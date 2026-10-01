package com.brac.automation.platform.application;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.UUID;
public final class ApplicationDtos {
    private ApplicationDtos() {}
    public record CreateRequest(@NotBlank @Size(max=200) String name, @Size(max=2000) String description) {}
    public record UpdateRequest(@NotBlank @Size(max=200) String name, @Size(max=2000) String description,
        @NotBlank @Pattern(regexp="ACTIVE|ARCHIVED") String status) {}
    public record Response(UUID id, UUID workspaceId, String name, String description, String status, Instant createdAt) {}
}
