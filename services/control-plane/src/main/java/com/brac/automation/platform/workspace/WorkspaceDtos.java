package com.brac.automation.platform.workspace;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;

public final class WorkspaceDtos {
    private WorkspaceDtos() {}
    public record CreateRequest(
        @NotBlank @Size(max=200) String name,
        @NotBlank @Pattern(regexp="[A-Za-z0-9][A-Za-z0-9_-]{1,39}") String key,
        @Size(max=1000) String description) {}
    public record UpdateRequest(
        @NotBlank @Size(max=200) String name,
        @NotBlank @Pattern(regexp="[A-Za-z0-9][A-Za-z0-9_-]{1,39}") String key,
        @Size(max=1000) String description) {}
    public record Response(UUID id, String key, String name, String description, String status, Instant createdAt, WorkspaceRole role) {}
    public record MemberResponse(UUID userId, String email, String displayName, WorkspaceRole role) {}
    public record AddMemberRequest(@NotBlank String email, @NotNull WorkspaceRole role) {}
}
