package com.brac.automation.platform.audit;

import com.brac.automation.platform.security.CurrentUserService;
import tools.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuditService {
    private final AuditEventRepository repository;
    private final CurrentUserService currentUser;
    private final ObjectMapper mapper;
    public AuditService(AuditEventRepository repository, CurrentUserService currentUser, ObjectMapper mapper) {
        this.repository = repository; this.currentUser = currentUser; this.mapper = mapper;
    }

    @Transactional
    public void success(UUID workspaceId, String action, String resourceType, UUID resourceId, Map<String, ?> metadata) {
        UUID actor = currentUser.currentUser().getId();
        repository.save(new AuditEvent(workspaceId, actor, action, resourceType, resourceId, "SUCCESS", toJson(metadata)));
    }

    private String toJson(Map<String, ?> metadata) {
        try { return metadata == null ? null : mapper.writeValueAsString(metadata); }
        catch (RuntimeException ex) { return "{\"metadataSerialization\":\"failed\"}"; }
    }
}
