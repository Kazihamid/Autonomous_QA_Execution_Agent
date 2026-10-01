package com.brac.automation.platform.security;

import com.brac.automation.platform.iam.UserAccount;
import com.brac.automation.platform.iam.UserAccountService;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

@Service
public class CurrentUserService {
    private final UserAccountService users;
    public CurrentUserService(UserAccountService users) { this.users = users; }

    public UserAccount currentUser() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth == null || !auth.isAuthenticated()) throw new AccessDeniedException("Authentication required.");
        Object principal = auth.getPrincipal();
        if (principal instanceof PlatformPrincipal p) {
            return users.ensureUser(p.subject(), p.email(), p.displayName());
        }
        if (principal instanceof Jwt jwt) {
            String subject = jwt.getSubject();
            String email = first(jwt.getClaimAsString("email"), jwt.getClaimAsString("preferred_username"), subject);
            String name = first(jwt.getClaimAsString("name"), jwt.getClaimAsString("given_name"), email);
            return users.ensureUser(subject, email, name);
        }
        throw new AccessDeniedException("Unsupported authenticated principal.");
    }

    private String first(String... values) {
        for (String value : values) if (value != null && !value.isBlank()) return value;
        return "Unknown User";
    }
}
