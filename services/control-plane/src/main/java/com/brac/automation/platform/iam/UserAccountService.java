package com.brac.automation.platform.iam;

import java.util.Locale;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserAccountService {
    private final UserAccountRepository repository;
    public UserAccountService(UserAccountRepository repository) { this.repository = repository; }

    @Transactional
    public UserAccount ensureUser(String subject, String email, String displayName) {
        if (subject == null || subject.isBlank()) throw new AccessDeniedException("Identity subject is required.");
        String normalizedEmail = email == null || email.isBlank() ? subject + "@unknown.invalid" : email.trim().toLowerCase(Locale.ROOT);
        String normalizedName = displayName == null || displayName.isBlank() ? normalizedEmail : displayName.trim();
        UserAccount user = repository.findBySubject(subject).orElseGet(() -> new UserAccount(subject, normalizedEmail, normalizedName));
        user.synchronize(normalizedEmail, normalizedName);
        user = repository.save(user);
        if (!"ACTIVE".equals(user.getStatus())) throw new AccessDeniedException("User account is inactive.");
        return user;
    }
}
