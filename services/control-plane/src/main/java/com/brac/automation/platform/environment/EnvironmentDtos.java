package com.brac.automation.platform.environment;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
public final class EnvironmentDtos {
    private EnvironmentDtos() {}
    public record CreateRequest(@NotBlank @Size(max=120) String name,@NotBlank @Size(max=2048) String baseUrl,
        @NotBlank @Pattern(regexp="CHROMIUM|FIREFOX|WEBKIT") String defaultBrowser,boolean headlessDefault,boolean allowRecording,boolean allowExecution) {}
    public record UpdateRequest(@NotBlank @Size(max=120) String name,@NotBlank @Size(max=2048) String baseUrl,
        @NotBlank @Pattern(regexp="CHROMIUM|FIREFOX|WEBKIT") String defaultBrowser,boolean headlessDefault,boolean allowRecording,boolean allowExecution,
        @NotBlank @Pattern(regexp="ACTIVE|INACTIVE") String status) {}
    public record Response(UUID id,UUID applicationId,String name,String baseUrl,String defaultBrowser,boolean headlessDefault,boolean allowRecording,boolean allowExecution,String validationStatus,String status,Instant createdAt) {}
    public record TargetValidationRequest(@NotBlank @Size(max=2048) String url) {}
    public record TargetValidationResponse(boolean valid,boolean dnsResolved,List<String> resolvedAddresses,List<String> warnings) {}
}
