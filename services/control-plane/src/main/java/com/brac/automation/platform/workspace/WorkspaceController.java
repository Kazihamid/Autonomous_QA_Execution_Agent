package com.brac.automation.platform.workspace;

import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/workspaces")
public class WorkspaceController {
    private final WorkspaceService service;
    public WorkspaceController(WorkspaceService service) { this.service = service; }

    @GetMapping public List<WorkspaceDtos.Response> list() { return service.list(); }
    @PostMapping @ResponseStatus(HttpStatus.CREATED) public WorkspaceDtos.Response create(@Valid @RequestBody WorkspaceDtos.CreateRequest request) { return service.create(request); }
    @GetMapping("/{workspaceId}") public WorkspaceDtos.Response get(@PathVariable UUID workspaceId) { return service.get(workspaceId); }
    @PutMapping("/{workspaceId}") public WorkspaceDtos.Response update(@PathVariable UUID workspaceId, @Valid @RequestBody WorkspaceDtos.UpdateRequest request) { return service.update(workspaceId, request); }
    @DeleteMapping("/{workspaceId}") @ResponseStatus(HttpStatus.NO_CONTENT) public void remove(@PathVariable UUID workspaceId) { service.remove(workspaceId); }
    @GetMapping("/{workspaceId}/members") public List<WorkspaceDtos.MemberResponse> members(@PathVariable UUID workspaceId) { return service.members(workspaceId); }
    @PostMapping("/{workspaceId}/members") @ResponseStatus(HttpStatus.CREATED)
    public WorkspaceDtos.MemberResponse addMember(@PathVariable UUID workspaceId, @Valid @RequestBody WorkspaceDtos.AddMemberRequest request) { return service.addMember(workspaceId, request); }
}
