package com.brac.automation.platform.scenarioactions;

import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.codegen.CodeGeneratorDtos;
import com.brac.automation.platform.codegen.CodeGeneratorService;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.recorder.RecordingSessionEntity;
import com.brac.automation.platform.recorder.RecordingSessionRepository;
import com.brac.automation.platform.recorder.ScenarioVersionEntity;
import com.brac.automation.platform.recorder.ScenarioVersionRepository;
import com.brac.automation.platform.recorder.TestScenarioEntity;
import com.brac.automation.platform.recorder.TestScenarioRepository;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.springframework.stereotype.Service;
import tools.jackson.databind.ObjectMapper;

@Service
public class ScenarioActionsService {
    private static final String RUN_TARGET = "PLAYWRIGHT_PYTEST";

    private final TestScenarioRepository scenarios;
    private final ScenarioVersionRepository versions;
    private final RecordingSessionRepository sessions;
    private final ApplicationService applications;
    private final WorkspaceAccessGuard guard;
    private final CodeGeneratorService codeGenerator;
    private final RunnerClient runner;
    private final AuditService audit;
    private final ObjectMapper mapper;

    public ScenarioActionsService(TestScenarioRepository scenarios, ScenarioVersionRepository versions,
            RecordingSessionRepository sessions, ApplicationService applications, WorkspaceAccessGuard guard,
            CodeGeneratorService codeGenerator, RunnerClient runner, AuditService audit, ObjectMapper mapper) {
        this.scenarios = scenarios; this.versions = versions; this.sessions = sessions; this.applications = applications;
        this.guard = guard; this.codeGenerator = codeGenerator; this.runner = runner; this.audit = audit; this.mapper = mapper;
    }

    public byte[] bulkExport(UUID workspaceId, UUID applicationId, ScenarioActionsDtos.BulkExportRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        List<UUID> ids = distinct(request.scenarioIds());
        String target = request.target().trim().toUpperCase(Locale.ROOT);
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            List<Map<String, Object>> manifestItems = new ArrayList<>();
            Map<String, String> projectFiles = new LinkedHashMap<>();
            Map<String, String> envValues = new LinkedHashMap<>();
            List<String> testNgClasses = new ArrayList<>();
            int exported = 0;

            for (UUID scenarioId : ids) {
                TestScenarioEntity scenario = scenario(workspaceId, applicationId, scenarioId);
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("scenarioId", scenarioId.toString());
                item.put("scenarioName", scenario.getName());
                item.put("module", scenario.getModuleName());
                item.put("feature", scenario.getFeatureName());
                item.put("target", target);
                try {
                    CodeGeneratorDtos.ImplementationDetail detail = codeGenerator.generate(
                        workspaceId, applicationId, scenarioId, new CodeGeneratorDtos.GenerateRequest(target));
                    Map<String, String> scenarioFiles = new LinkedHashMap<>();
                    String metadataFolder = "scenarios/" + slug(scenario.getName()) + "-" + scenarioId.toString().substring(0, 8) + "/";
                    for (CodeGeneratorDtos.GeneratedFile generated : detail.files()) {
                        String generatedPath = safePath(generated.path());
                        String content = generated.content();
                        if (".env.example".equals(generatedPath)) {
                            for (String line : content.split("\\R")) {
                                if (line.isBlank() || !line.contains("=")) continue;
                                int p = line.indexOf('=');
                                String key = line.substring(0, p).trim();
                                String value = line.substring(p + 1);
                                envValues.putIfAbsent(key, value);
                            }
                            continue;
                        }
                        if ("automation-ir.json".equals(generatedPath) || "source-map.json".equals(generatedPath) || "README.md".equals(generatedPath)) {
                            scenarioFiles.put(metadataFolder + generatedPath, content);
                            continue;
                        }
                        if ("SELENIUM_TESTNG".equals(target) && "testng.xml".equals(generatedPath)) continue;
                        scenarioFiles.put(generatedPath, content);
                        if ("SELENIUM_TESTNG".equals(target) && generatedPath.startsWith("src/test/java/generated/tests/") && generatedPath.endsWith(".java")) {
                            String cls = generatedPath.substring("src/test/java/".length(), generatedPath.length() - ".java".length()).replace('/', '.');
                            testNgClasses.add(cls);
                        }
                    }
                    for (Map.Entry<String, String> e : scenarioFiles.entrySet()) {
                        String existing = projectFiles.get(e.getKey());
                        if (existing != null && !existing.equals(e.getValue())) {
                            throw new IllegalStateException("Generated file collision in combined project: " + e.getKey());
                        }
                    }
                    scenarioFiles.forEach(projectFiles::putIfAbsent);
                    item.put("status", "EXPORTED");
                    item.put("implementationId", detail.implementation().id().toString());
                    item.put("sourceHash", detail.implementation().sourceHash());
                    exported++;
                } catch (Exception ex) {
                    item.put("status", "SKIPPED");
                    item.put("error", ex.getMessage());
                }
                manifestItems.add(item);
            }

            if (!envValues.isEmpty()) {
                StringBuilder env = new StringBuilder();
                envValues.forEach((k, v) -> env.append(k).append('=').append(v).append('\n'));
                projectFiles.put(".env.example", env.toString());
            }
            if ("SELENIUM_TESTNG".equals(target) && !testNgClasses.isEmpty()) {
                StringBuilder suite = new StringBuilder("<!DOCTYPE suite SYSTEM \"https://testng.org/testng-1.0.dtd\">\n<suite name=\"Combined Automation\"><test name=\"Selected Scenarios\"><classes>\n");
                for (String cls : new LinkedHashSet<>(testNgClasses)) suite.append("<class name=\"").append(cls).append("\"/>\n");
                suite.append("</classes></test></suite>\n");
                projectFiles.put("testng.xml", suite.toString());
            }

            String runCommand = "PLAYWRIGHT_PYTEST".equals(target) ? "py -m pytest" : "mvn test";
            projectFiles.put("README.md",
                "# Combined Autonomous QA Execution Agent Project\n\n" +
                "This package contains all successfully generated selected scenarios in one runnable project.\n\n" +
                "Run: " + runCommand + "\n\n" +
                "Scenario-specific Automation IR and source maps are under scenarios/.\n" +
                "Check bulk-manifest.json for exported or skipped scenarios.\n");

            var manifest = mapper.createObjectNode();
            manifest.put("format", "ai-test-automation-combined-project-v2");
            manifest.put("target", target);
            manifest.put("selectedCount", ids.size());
            manifest.put("exportedCount", exported);
            manifest.put("skippedCount", ids.size() - exported);
            manifest.set("scenarios", mapper.valueToTree(manifestItems));
            projectFiles.put("bulk-manifest.json", mapper.writerWithDefaultPrettyPrinter().writeValueAsString(manifest));

            try (ZipOutputStream zip = new ZipOutputStream(bytes, StandardCharsets.UTF_8)) {
                for (Map.Entry<String, String> projectFile : projectFiles.entrySet()) {
                    zip.putNextEntry(new ZipEntry(safePath(projectFile.getKey())));
                    zip.write(projectFile.getValue().getBytes(StandardCharsets.UTF_8));
                    zip.closeEntry();
                }
            }
            audit.success(workspaceId, "SCENARIO_BULK_EXPORTED", "APPLICATION", applicationId,
                Map.of("selected", ids.size(), "exported", exported, "skipped", ids.size() - exported, "target", target));
            return bytes.toByteArray();
        } catch (RuntimeException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new IllegalStateException("Could not build combined scenario export: " + ex.getMessage(), ex);
        }
    }

    public ScenarioActionsDtos.BulkRunResponse run(UUID workspaceId, UUID applicationId, ScenarioActionsDtos.RunRequest request) {
        guard.requireWrite(workspaceId); applications.entity(workspaceId, applicationId);
        List<UUID> ids = distinct(request.scenarioIds());
        List<ScenarioActionsDtos.RunResult> results = new ArrayList<>();
        for (UUID scenarioId : ids) {
            TestScenarioEntity scenario = scenario(workspaceId, applicationId, scenarioId);
            try {
                CodeGeneratorDtos.ImplementationDetail detail = codeGenerator.generate(
                    workspaceId, applicationId, scenarioId, new CodeGeneratorDtos.GenerateRequest(RUN_TARGET));
                String baseUrl = baseUrl(workspaceId, applicationId, scenarioId);
                results.add(runner.run(scenarioId, scenario.getName(), baseUrl, detail.files()));
            } catch (Exception ex) {
                results.add(new ScenarioActionsDtos.RunResult(scenarioId, scenario.getName(), "ERROR", null, 0, "", ex.getMessage()));
            }
        }
        int passed = (int) results.stream().filter(r -> "PASSED".equals(r.status())).count();
        int failed = results.size() - passed;
        audit.success(workspaceId, "SCENARIO_RUN_REQUESTED", "APPLICATION", applicationId,
            Map.of("count", ids.size(), "passed", passed, "failed", failed));
        return new ScenarioActionsDtos.BulkRunResponse(results.size(), passed, failed, results);
    }

    private String baseUrl(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        ScenarioVersionEntity version = versions.findFirstByScenarioIdOrderByVersionNoDesc(scenarioId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario version not found."));
        UUID sourceId = version.getSourceRecordingSessionId();
        if (sourceId != null) {
            RecordingSessionEntity session = sessions.findByIdAndWorkspaceIdAndApplicationId(sourceId, workspaceId, applicationId).orElse(null);
            if (session != null && session.getStartUrl() != null && !session.getStartUrl().isBlank()) return session.getStartUrl();
        }
        try {
            var ir = mapper.readTree(version.getAutomationIr());
            for (var step : ir.path("steps")) {
                if ("navigate".equals(step.path("action").asText()) && !step.path("url").asText("").isBlank()) return step.path("url").asText();
            }
        } catch (Exception ignored) {}
        throw new IllegalStateException("Could not determine a target Base URL for this scenario.");
    }

    private TestScenarioEntity scenario(UUID workspaceId, UUID applicationId, UUID scenarioId) {
        return scenarios.findByIdAndWorkspaceIdAndApplicationId(scenarioId, workspaceId, applicationId)
            .orElseThrow(() -> new ResourceNotFoundException("Scenario not found."));
    }

    private List<UUID> distinct(List<UUID> ids) { return new ArrayList<>(new LinkedHashSet<>(ids)); }

    private String safePath(String value) {
        String path = value.replace('\\', '/');
        if (path.startsWith("/") || path.contains("../")) throw new IllegalArgumentException("Unsafe generated path: " + value);
        return path;
    }

    private String slug(String value) {
        String s = value == null ? "scenario" : value.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "-").replaceAll("(^-|-$)", "");
        return s.isBlank() ? "scenario" : s;
    }
}