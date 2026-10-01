package com.brac.automation.platform.workspace;

import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.common.ConflictException;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.iam.UserAccount;
import com.brac.automation.platform.iam.UserAccountRepository;
import com.brac.automation.platform.security.CurrentUserService;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorkspaceService {
    private final WorkspaceRepository workspaces;
    private final WorkspaceMemberRepository members;
    private final UserAccountRepository users;
    private final CurrentUserService currentUser;
    private final WorkspaceAccessGuard guard;
    private final AuditService audit;

    public WorkspaceService(WorkspaceRepository workspaces, WorkspaceMemberRepository members, UserAccountRepository users,
            CurrentUserService currentUser, WorkspaceAccessGuard guard, AuditService audit) {
        this.workspaces = workspaces; this.members = members; this.users = users; this.currentUser = currentUser; this.guard = guard; this.audit = audit;
    }

    @Transactional
    public WorkspaceDtos.Response create(WorkspaceDtos.CreateRequest request) {
        UserAccount user = currentUser.currentUser();
        String key = request.key().trim().toUpperCase(Locale.ROOT);
        if (workspaces.existsByWorkspaceKeyIgnoreCase(key)) throw new ConflictException("Workspace key already exists.");
        Workspace workspace = workspaces.save(new Workspace(key, request.name().trim(), clean(request.description()), user.getId()));
        WorkspaceMember member = members.save(new WorkspaceMember(workspace.getId(), user.getId(), WorkspaceRole.ADMINISTRATOR));
        audit.success(workspace.getId(), "WORKSPACE_CREATED", "WORKSPACE", workspace.getId(), Map.of("key", key));
        return response(workspace, member.getRole());
    }

    @Transactional(readOnly = true)
    public List<WorkspaceDtos.Response> list() {
        UUID userId = currentUser.currentUser().getId();
        return members.findByUserIdAndActiveTrue(userId).stream()
            .map(m -> workspaces.findByIdAndStatus(m.getWorkspaceId(), "ACTIVE").map(w -> response(w, m.getRole())).orElse(null))
            .filter(r -> r != null)
            .sorted(Comparator.comparing(WorkspaceDtos.Response::name, String.CASE_INSENSITIVE_ORDER))
            .toList();
    }

    @Transactional(readOnly = true)
    public WorkspaceDtos.Response get(UUID workspaceId) {
        WorkspaceMember member = guard.requireRead(workspaceId);
        Workspace workspace = workspaces.findByIdAndStatus(workspaceId, "ACTIVE").orElseThrow(() -> new ResourceNotFoundException("Workspace not found."));
        return response(workspace, member.getRole());
    }


    @Transactional
    public WorkspaceDtos.Response update(UUID workspaceId, WorkspaceDtos.UpdateRequest request) {
        WorkspaceMember member = guard.requireAny(workspaceId, WorkspaceRole.ADMINISTRATOR);
        Workspace workspace = workspaces.findByIdAndStatus(workspaceId, "ACTIVE").orElseThrow(() -> new ResourceNotFoundException("Workspace not found."));
        String key = request.key().trim().toUpperCase(Locale.ROOT);
        if (workspaces.existsByWorkspaceKeyIgnoreCaseAndIdNot(key, workspaceId)) throw new ConflictException("Workspace key already exists.");
        workspace.update(key, request.name().trim(), clean(request.description()));
        workspaces.save(workspace);
        audit.success(workspaceId, "WORKSPACE_UPDATED", "WORKSPACE", workspaceId, Map.of("key", key));
        return response(workspace, member.getRole());
    }

    @Transactional
    public void remove(UUID workspaceId) {
        guard.requireAny(workspaceId, WorkspaceRole.ADMINISTRATOR);
        Workspace workspace = workspaces.findByIdAndStatus(workspaceId, "ACTIVE").orElseThrow(() -> new ResourceNotFoundException("Workspace not found."));
        workspace.archive();
        workspaces.save(workspace);
        for (WorkspaceMember member : members.findByWorkspaceIdAndActiveTrueOrderByCreatedAtAsc(workspaceId)) {
            member.deactivate();
            members.save(member);
        }
        audit.success(workspaceId, "WORKSPACE_REMOVED", "WORKSPACE", workspaceId, Map.of("status", "DELETED"));
    }

    @Transactional(readOnly = true)
    public List<WorkspaceDtos.MemberResponse> members(UUID workspaceId) {
        guard.requireRead(workspaceId);
        return members.findByWorkspaceIdAndActiveTrueOrderByCreatedAtAsc(workspaceId).stream().map(m -> {
            UserAccount user = users.findById(m.getUserId()).orElseThrow();
            return new WorkspaceDtos.MemberResponse(user.getId(), user.getEmail(), user.getDisplayName(), m.getRole());
        }).toList();
    }

    @Transactional
    public WorkspaceDtos.MemberResponse addMember(UUID workspaceId, WorkspaceDtos.AddMemberRequest request) {
        guard.requireAny(workspaceId, WorkspaceRole.ADMINISTRATOR);
        UserAccount user = users.findByEmailIgnoreCase(request.email().trim()).orElseThrow(() -> new ResourceNotFoundException("User must sign in at least once before being added to a workspace."));
        WorkspaceMember member = members.findByWorkspaceIdAndUserIdAndActiveTrue(workspaceId, user.getId()).orElseGet(() -> members.save(new WorkspaceMember(workspaceId, user.getId(), request.role())));
        member.changeRole(request.role());
        members.save(member);
        audit.success(workspaceId, "WORKSPACE_MEMBER_UPSERTED", "USER", user.getId(), Map.of("role", request.role().name()));
        return new WorkspaceDtos.MemberResponse(user.getId(), user.getEmail(), user.getDisplayName(), member.getRole());
    }

    private WorkspaceDtos.Response response(Workspace w, WorkspaceRole role) {
        return new WorkspaceDtos.Response(w.getId(), w.getWorkspaceKey(), w.getName(), w.getDescription(), w.getStatus(), w.getCreatedAt(), role);
    }
    private String clean(String v) { return v == null || v.isBlank() ? null : v.trim(); }
}
