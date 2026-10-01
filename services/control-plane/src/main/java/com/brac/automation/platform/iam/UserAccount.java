package com.brac.automation.platform.iam;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(schema = "iam", name = "user_account")
public class UserAccount {
    @Id private UUID id;
    @Column(nullable = false, unique = true) private String subject;
    @Column(nullable = false) private String email;
    @Column(name = "display_name", nullable = false) private String displayName;
    @Column(nullable = false) private String status;
    @Column(name = "created_at", nullable = false) private Instant createdAt;
    @Column(name = "updated_at", nullable = false) private Instant updatedAt;

    protected UserAccount() {}

    public UserAccount(String subject, String email, String displayName) {
        this.id = UUID.randomUUID();
        this.subject = subject;
        this.email = email;
        this.displayName = displayName;
        this.status = "ACTIVE";
        this.createdAt = Instant.now();
        this.updatedAt = this.createdAt;
    }

    public void synchronize(String email, String displayName) {
        this.email = email;
        this.displayName = displayName;
        this.updatedAt = Instant.now();
    }

    public UUID getId() { return id; }
    public String getSubject() { return subject; }
    public String getEmail() { return email; }
    public String getDisplayName() { return displayName; }
    public String getStatus() { return status; }
}
