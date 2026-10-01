package com.brac.automation.platform.workspace;

import com.brac.automation.platform.security.CurrentUserService;
import java.util.Arrays;
import java.util.UUID;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Component;

@Component
public class WorkspaceAccessGuard {
    private final WorkspaceMemberRepository members;
    private final CurrentUserService currentUser;
    public WorkspaceAccessGuard(WorkspaceMemberRepository members, CurrentUserService currentUser) {
        this.members = members; this.currentUser = currentUser;
    }

    public WorkspaceMember requireAny(UUID workspaceId, WorkspaceRole... allowed) {
        UUID userId = currentUser.currentUser().getId();
        WorkspaceMember member = members.findByWorkspaceIdAndUserIdAndActiveTrue(workspaceId, userId)
            .orElseThrow(() -> new AccessDeniedException("Workspace access denied."));
        if (allowed.length > 0 && Arrays.stream(allowed).noneMatch(r -> r == member.getRole())) {
            throw new AccessDeniedException("Workspace role does not permit this operation.");
        }
        return member;
    }

    public WorkspaceMember requireRead(UUID workspaceId) {
        return requireAny(workspaceId, WorkspaceRole.ADMINISTRATOR, WorkspaceRole.QA_LEAD, WorkspaceRole.QA_ENGINEER,
            WorkspaceRole.AUTOMATION_ENGINEER, WorkspaceRole.VIEWER);
    }

    public WorkspaceMember requireWrite(UUID workspaceId) {
        return requireAny(workspaceId, WorkspaceRole.ADMINISTRATOR, WorkspaceRole.QA_LEAD, WorkspaceRole.QA_ENGINEER,
            WorkspaceRole.AUTOMATION_ENGINEER);
    }
}
