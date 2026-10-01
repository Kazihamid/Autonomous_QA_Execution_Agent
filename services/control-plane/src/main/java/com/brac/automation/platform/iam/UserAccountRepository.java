package com.brac.automation.platform.iam;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserAccountRepository extends JpaRepository<UserAccount, UUID> {
    Optional<UserAccount> findBySubject(String subject);
    Optional<UserAccount> findByEmailIgnoreCase(String email);
}
