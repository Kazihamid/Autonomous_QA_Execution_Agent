package com.brac.automation.platform.security;

import java.util.List;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

public final class SecuritySupport {
    private static final java.util.regex.Pattern PRIVATE_WEB_ORIGIN = java.util.regex.Pattern.compile(
        "^http://(localhost|127\\.0\\.0\\.1|10\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|192\\.168\\.\\d{1,3}\\.\\d{1,3}|172\\.(1[6-9]|2\\d|3[01])\\.\\d{1,3}\\.\\d{1,3}|169\\.254\\.\\d{1,3}\\.\\d{1,3}|100\\.(6[4-9]|[7-9]\\d|1[01]\\d|12[0-7])\\.\\d{1,3}\\.\\d{1,3}|[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*\\.ts\\.net|[A-Za-z0-9-]+):3000$");

    private SecuritySupport() {}

    public static CorsConfigurationSource corsConfigurationSource() {
        final boolean allowPrivate = !"false".equalsIgnoreCase(System.getenv("CORS_ALLOW_PRIVATE_NETWORK"));
        CorsConfiguration config = new CorsConfiguration() {
            @Override
            public String checkOrigin(String requestOrigin) {
                String allowed = super.checkOrigin(requestOrigin);
                if (allowed != null) {
                    return allowed;
                }
                // The web page may be opened by any address of this machine (localhost, office network, VPN, hotspot or its computer name).
                if (allowPrivate && requestOrigin != null && PRIVATE_WEB_ORIGIN.matcher(requestOrigin).matches()) {
                    return requestOrigin;
                }
                return null;
            }
        };
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
