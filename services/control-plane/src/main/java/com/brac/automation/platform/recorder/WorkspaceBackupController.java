package com.brac.automation.platform.recorder;

import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import tools.jackson.databind.JsonNode;

@RestController
@RequestMapping("/api/v1/workspaces")
public class WorkspaceBackupController {
    private final WorkspaceBackupService service;

    public WorkspaceBackupController(WorkspaceBackupService service) { this.service = service; }

    @GetMapping("/{workspaceId}/backup")
    public JsonNode backup(@PathVariable UUID workspaceId) { return service.backup(workspaceId); }

    /** Creates a new workspace for the signed-in user from a workspace backup file. */
    @PostMapping("/backup/import") @ResponseStatus(HttpStatus.CREATED)
    public RecoveryDtos.WorkspaceImportResult importNew(@RequestBody JsonNode document) { return service.importAsNewWorkspace(document); }

    @PostMapping("/{workspaceId}/backup/import")
    public RecoveryDtos.WorkspaceImportResult importInto(@PathVariable UUID workspaceId, @RequestBody JsonNode document) { return service.importIntoWorkspace(workspaceId, document); }
}
