package com.brac.automation.platform.scenarioactions;

import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications/{applicationId}/scenario-actions")
public class ScenarioActionsController {
    private final ScenarioActionsService service;
    private final RunJobService jobs;
    public ScenarioActionsController(ScenarioActionsService service, RunJobService jobs) { this.service = service; this.jobs = jobs; }

    @PostMapping(value = "/export", produces = "application/zip")
    public ResponseEntity<byte[]> export(@PathVariable UUID workspaceId, @PathVariable UUID applicationId,
            @Valid @RequestBody ScenarioActionsDtos.BulkExportRequest request) {
        byte[] zip = service.bulkExport(workspaceId, applicationId, request);
        return ResponseEntity.ok()
            .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=combined-automation-project.zip")
            .contentType(MediaType.parseMediaType("application/zip"))
            .body(zip);
    }

    @PostMapping("/run")
    public ScenarioActionsDtos.BulkRunResponse run(@PathVariable UUID workspaceId, @PathVariable UUID applicationId,
            @Valid @RequestBody ScenarioActionsDtos.RunRequest request) {
        return service.run(workspaceId, applicationId, request);
    }

    @PostMapping("/run-jobs") @ResponseStatus(HttpStatus.ACCEPTED)
    public ScenarioActionsDtos.RunJobView startRunJob(@PathVariable UUID workspaceId, @PathVariable UUID applicationId,
            @Valid @RequestBody ScenarioActionsDtos.RunRequest request) {
        return jobs.start(workspaceId, applicationId, request);
    }

    @GetMapping("/run-jobs/{jobId}")
    public ScenarioActionsDtos.RunJobView getRunJob(@PathVariable UUID workspaceId, @PathVariable UUID applicationId, @PathVariable UUID jobId) {
        return jobs.get(workspaceId, applicationId, jobId);
    }
}
