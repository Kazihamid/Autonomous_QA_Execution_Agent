package com.brac.automation.platform.security;

import java.util.List;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

public final class SecuritySupport {
    private SecuritySupport() {}

    public static CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();
        String configured = System.getenv("CORS_ALLOWED_ORIGINS");
        List<String> origins = (configured == null || configured.isBlank())
            ? List.of("http://localhost:3000")
            : java.util.Arrays.stream(configured.split(",")).map(String::trim).filter(x -> !x.isEmpty()).toList();
        config.setAllowedOrigins(origins);
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        config.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Dev-User-Sub", "X-Dev-User-Email", "X-Dev-User-Name", "Idempotency-Key"));
        config.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
