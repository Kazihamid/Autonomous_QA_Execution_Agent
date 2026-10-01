package com.brac.automation.platform.audit;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
public interface AuditEventRepository extends JpaRepository<AuditEvent, UUID> {}
