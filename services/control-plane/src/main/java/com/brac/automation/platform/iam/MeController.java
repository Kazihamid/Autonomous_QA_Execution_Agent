package com.brac.automation.platform.iam;

import com.brac.automation.platform.security.CurrentUserService;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/me")
public class MeController {
    private final CurrentUserService currentUser;
    public MeController(CurrentUserService currentUser) { this.currentUser = currentUser; }

    @GetMapping
    public Map<String, Object> me() {
        UserAccount user = currentUser.currentUser();
        return Map.of(
            "id", user.getId(),
            "email", user.getEmail(),
            "displayName", user.getDisplayName(),
            "status", user.getStatus());
    }
}
