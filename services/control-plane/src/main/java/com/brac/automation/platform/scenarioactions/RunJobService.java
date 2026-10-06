package com.brac.automation.platform.scenarioactions;

import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.codegen.CodeGeneratorDtos;
import com.brac.automation.platform.codegen.CodeGeneratorService;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.environment.EnvironmentEntity;
import com.brac.automation.platform.environment.EnvironmentService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import jakarta.annotation.PreDestroy;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.concurrent.DelegatingSecurityContextExecutorService;
import org.springframework.stereotype.Service;

/**
 * Runs scenarios as background jobs so the UI can show live progress.
 * Jobs are held in memory (last 50); they are not persisted across Control Plane restarts.
 * The executor propagates the submitting user's SecurityContext, because code generation and
 * auditing resolve the current user.
 */
@Service
public class RunJobService {
    private static final Logger log = LoggerFactory.getLogger(RunJobService.class);
    private static final String RUN_TARGET = "PLAYWRIGHT_PYTEST";
    private static final int TEST_TIMEOUT_SECONDS = 180;
    private static final int MAX_JOBS = 50;

    private final ScenarioActionsService scenarios;
    private final ApplicationService applications;
    private final EnvironmentService environments;
    private final CodeGeneratorService codeGenerator;
    private final RunnerClient runner;
    private final WorkspaceAccessGuard guard;
    private final AuditService audit;
    private final ExecutorService executor =
        new DelegatingSecurityContextExecutorService(Executors.newFixedThreadPool(2));
    private final Map<UUID, Job> jobs = new LinkedHashMap<>();

    public RunJobService(ScenarioActionsService scenarios, ApplicationService applications, EnvironmentService environments,
            CodeGeneratorService codeGenerator, RunnerClient runner, WorkspaceAccessGuard guard, AuditService audit) {
        this.scenarios = scenarios; this.applications = applications; this.environments = environments;
        this.codeGenerator = codeGenerator; this.runner = runner; this.guard = guard; this.audit = audit;
    }

    @PreDestroy
    void shutdown() { executor.shutdownNow(); }

    public ScenarioActionsDtos.RunJobView start(UUID workspaceId, UUID applicationId, ScenarioActionsDtos.RunRequest request) {
        guard.requireWrite(workspaceId);
        applications.entity(workspaceId, applicationId);
        EnvironmentEntity env = request.environmentId() == null ? null
            : environments.requireExecutable(workspaceId, applicationId, request.environmentId());
        List<UUID> ids = scenarios.inExecutionOrder(workspaceId, applicationId, scenarios.distinct(request.scenarioIds()));
        Job job = new Job(workspaceId, applicationId, env == null ? null : env.getId(), env == null ? null : env.getName(),
            env == null ? null : env.getBaseUrl(), Boolean.TRUE.equals(request.stopOnFailure()));
        for (UUID id : ids) job.items.add(new Item(id, scenarios.scenario(workspaceId, applicationId, id).getName()));
        synchronized (jobs) {
            jobs.put(job.id, job);
            while (jobs.size() > MAX_JOBS) jobs.remove(jobs.keySet().iterator().next());
        }
        executor.submit(() -> execute(job));
        return job.view();
    }

    public ScenarioActionsDtos.RunJobView get(UUID workspaceId, UUID applicationId, UUID jobId) {
        guard.requireRead(workspaceId);
        Job job;
        synchronized (jobs) { job = jobs.get(jobId); }
        if (job == null || !job.workspaceId.equals(workspaceId) || !job.applicationId.equals(applicationId)) {
            throw new ResourceNotFoundException("Run job not found (it may have been cleared after a restart).");
        }
        return job.view();
    }

    private void execute(Job job) {
        job.markRunning();
        String stoppedBy = null;
        try {
            for (Item item : job.items) {
                if (stoppedBy != null) {
                    item.finish("SKIPPED", "Skipped: stop-on-failure is on and \"" + stoppedBy + "\" did not pass.");
                    continue;
                }
                runOne(job, item);
                if (job.stopOnFailure && !"PASSED".equals(item.status)) stoppedBy = item.name;
            }
        } catch (RuntimeException ex) {
            log.warn("Run job {} failed unexpectedly", job.id, ex);
            for (Item item : job.items) if (!item.isDone()) item.finish("ERROR", String.valueOf(ex.getMessage()));
        } finally {
            job.complete();
            try {
                ScenarioActionsDtos.RunJobView v = job.view();
                audit.success(job.workspaceId, "SCENARIO_RUN_JOB_COMPLETED", "APPLICATION", job.applicationId,
                    Map.of("jobId", job.id.toString(), "total", v.total(), "passed", v.passed(), "failed", v.failed(),
                        "skipped", v.skipped(), "environment", String.valueOf(job.environmentName)));
            } catch (RuntimeException ex) {
                log.warn("Could not audit run job {}", job.id, ex);
            }
        }
    }

    private void runOne(Job job, Item item) {
        try {
            item.setStatus("GENERATING");
            CodeGeneratorDtos.ImplementationDetail detail = codeGenerator.generate(
                job.workspaceId, job.applicationId, item.scenarioId, new CodeGeneratorDtos.GenerateRequest(RUN_TARGET));
            String baseUrl = job.baseUrl != null ? job.baseUrl : scenarios.baseUrl(job.workspaceId, job.applicationId, item.scenarioId);
            item.setStatus("RUNNING");
            String runId = runner.start(item.scenarioId, item.name, baseUrl, TEST_TIMEOUT_SECONDS, detail.files());
            long deadline = System.currentTimeMillis() + (TEST_TIMEOUT_SECONDS + 60) * 1000L;
            while (true) {
                RunnerClient.RunnerRunStatus st = runner.poll(runId);
                item.update(st);
                if (st.terminal()) {
                    item.finish(st.status(), st.message());
                    return;
                }
                if (System.currentTimeMillis() > deadline) {
                    item.finish("TIMED_OUT", "The runner did not finish in time.");
                    return;
                }
                Thread.sleep(700);
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            item.finish("ERROR", "Run interrupted.");
        } catch (Exception ex) {
            item.finish("ERROR", String.valueOf(ex.getMessage()));
        }
    }

    // ---- in-memory state --------------------------------------------------------------------

    private static final class Item {
        final UUID scenarioId; final String name;
        volatile String status = "QUEUED"; volatile String output = ""; volatile String message = "";
        volatile int currentStep; volatile int totalSteps; volatile String currentAction = "";
        volatile Instant startedAt; volatile long durationMs; private volatile boolean done;

        Item(UUID scenarioId, String name) { this.scenarioId = scenarioId; this.name = name; }
        void setStatus(String s) { if (startedAt == null) startedAt = Instant.now(); status = s; }
        boolean isDone() { return done; }
        void update(RunnerClient.RunnerRunStatus st) {
            output = st.output(); currentStep = st.currentStep(); totalSteps = st.totalSteps();
            currentAction = st.currentAction(); durationMs = st.durationMs();
        }
        void finish(String s, String msg) {
            status = s; message = msg == null ? "" : msg; done = true;
            if (startedAt != null && durationMs == 0) durationMs = Instant.now().toEpochMilli() - startedAt.toEpochMilli();
        }
        ScenarioActionsDtos.RunItemView view() {
            long d = done || startedAt == null ? durationMs : Instant.now().toEpochMilli() - startedAt.toEpochMilli();
            return new ScenarioActionsDtos.RunItemView(scenarioId, name, status, currentStep, totalSteps, currentAction,
                startedAt, d, output, message);
        }
    }

    private static final class Job {
        final UUID id = UUID.randomUUID();
        final UUID workspaceId; final UUID applicationId; final UUID environmentId; final String environmentName; final String baseUrl;
        final boolean stopOnFailure; final List<Item> items = new ArrayList<>();
        volatile String status = "QUEUED"; volatile Instant startedAt; volatile Instant finishedAt;

        Job(UUID workspaceId, UUID applicationId, UUID environmentId, String environmentName, String baseUrl, boolean stopOnFailure) {
            this.workspaceId = workspaceId; this.applicationId = applicationId; this.environmentId = environmentId;
            this.environmentName = environmentName; this.baseUrl = baseUrl; this.stopOnFailure = stopOnFailure;
        }
        void markRunning() { status = "RUNNING"; startedAt = Instant.now(); }
        void complete() { status = "COMPLETED"; finishedAt = Instant.now(); }
        ScenarioActionsDtos.RunJobView view() {
            List<ScenarioActionsDtos.RunItemView> views = items.stream().map(Item::view).toList();
            int passed = (int) views.stream().filter(v -> "PASSED".equals(v.status())).count();
            int skipped = (int) views.stream().filter(v -> "SKIPPED".equals(v.status())).count();
            int failed = (int) views.stream().filter(v -> List.of("FAILED", "ERROR", "TIMED_OUT").contains(v.status())).count();
            return new ScenarioActionsDtos.RunJobView(id, status, environmentId, environmentName, baseUrl, stopOnFailure,
                startedAt, finishedAt, views.size(), passed + failed + skipped, passed, failed, skipped, views);
        }
    }
}
