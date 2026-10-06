package com.brac.automation.platform.security;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

/**
 * Fails fast when the header-based dev authentication (X-Dev-User-Sub) is active
 * outside a local environment. Anyone who can reach the API could otherwise
 * impersonate any user.
 */
@Configuration
@Profile("dev")
public class DevProfileGuard {
    private final String platformEnv;

    public DevProfileGuard(@Value("${PLATFORM_ENV:}") String platformEnv) {
        this.platformEnv = platformEnv;
    }

    @PostConstruct
    void verify() {
        check(platformEnv);
    }

    static void check(String platformEnv) {
        if (!"local".equalsIgnoreCase(platformEnv == null ? "" : platformEnv.trim())) {
            throw new IllegalStateException(
                "The 'dev' Spring profile enables header-based authentication and is only allowed when "
                + "PLATFORM_ENV=local (current: '" + platformEnv + "'). Use a non-dev profile with OIDC instead.");
        }
    }
}
