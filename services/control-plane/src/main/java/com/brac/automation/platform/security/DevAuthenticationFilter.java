package com.brac.automation.platform.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

@Component
public class DevAuthenticationFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        if (SecurityContextHolder.getContext().getAuthentication() == null) {
            String subject = value(request, "X-Dev-User-Sub", "dev-user-001");
            String email = value(request, "X-Dev-User-Email", "qa.engineer@example.invalid");
            String name = value(request, "X-Dev-User-Name", "QA Engineer");
            PlatformPrincipal principal = new PlatformPrincipal(subject, email, name);
            var auth = new UsernamePasswordAuthenticationToken(
                principal, null, List.of(new SimpleGrantedAuthority("ROLE_AUTHENTICATED")));
            SecurityContextHolder.getContext().setAuthentication(auth);
        }
        filterChain.doFilter(request, response);
    }

    private String value(HttpServletRequest request, String header, String fallback) {
        String value = request.getHeader(header);
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
