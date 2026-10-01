package com.brac.automation.platform.environment;

import com.brac.automation.platform.common.PolicyViolationException;
import java.net.InetAddress;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import org.springframework.stereotype.Component;

@Component
public class EnvironmentTargetValidator {
    private static final List<String> METADATA_HOSTS = List.of("169.254.169.254", "metadata.google.internal", "metadata.azure.internal");
    private final TargetPolicyProperties properties;
    public EnvironmentTargetValidator(TargetPolicyProperties properties){this.properties=properties;}

    public TargetValidationResult validate(String rawUrl) {
        URI uri;
        try { uri = new URI(rawUrl); }
        catch (URISyntaxException ex) { throw new PolicyViolationException("Environment base URL is not a valid URI."); }
        String scheme = uri.getScheme();
        if (scheme == null || !(scheme.equalsIgnoreCase("http") || scheme.equalsIgnoreCase("https"))) {
            throw new PolicyViolationException("Only HTTP and HTTPS environment targets are allowed.");
        }
        if (uri.getUserInfo() != null) throw new PolicyViolationException("Credentials must not be embedded in environment URLs.");
        String host = uri.getHost();
        if (host == null || host.isBlank()) throw new PolicyViolationException("Environment URL must include a hostname.");
        host = host.toLowerCase(Locale.ROOT);
        if (host.equals("localhost") || host.endsWith(".localhost") || METADATA_HOSTS.contains(host)) {
            throw new PolicyViolationException("Environment target is blocked by SSRF policy.");
        }
        requireAllowlist(host);

        List<String> addresses = new ArrayList<>();
        List<String> warnings = new ArrayList<>();
        try {
            InetAddress[] resolved = InetAddress.getAllByName(host);
            for (InetAddress address : resolved) {
                enforceAddress(address);
                addresses.add(address.getHostAddress());
            }
            if (addresses.isEmpty()) warnings.add("DNS resolution returned no addresses.");
            return new TargetValidationResult(true, !addresses.isEmpty(), List.copyOf(addresses), List.copyOf(warnings));
        } catch (UnknownHostException ex) {
            warnings.add("DNS could not be resolved from the Control Plane. Recorder/Runner must revalidate the target at execution time.");
            return new TargetValidationResult(true, false, List.of(), List.copyOf(warnings));
        }
    }

    private void requireAllowlist(String host) {
        List<String> configured = properties.getAllowedHosts().stream().map(String::trim).filter(s -> !s.isBlank()).toList();
        if (configured.isEmpty()) return;
        boolean allowed = configured.stream().anyMatch(pattern -> {
            String p = pattern.toLowerCase(Locale.ROOT);
            if (p.startsWith("*.")) return host.endsWith(p.substring(1));
            return host.equals(p);
        });
        if (!allowed) throw new PolicyViolationException("Environment hostname is not in the configured target allowlist.");
    }

    private void enforceAddress(InetAddress address) {
        if (address.isAnyLocalAddress() || address.isLoopbackAddress() || address.isLinkLocalAddress() || address.isMulticastAddress()) {
            throw new PolicyViolationException("Resolved environment target is blocked by network policy.");
        }
        if (isMetadata(address)) throw new PolicyViolationException("Cloud metadata endpoints are blocked.");
        if (!properties.isAllowPrivateTargets() && (address.isSiteLocalAddress() || isIpv6UniqueLocal(address))) {
            throw new PolicyViolationException("Private environment targets are disabled by default. Enable only with explicit deployment policy and egress controls.");
        }
    }

    private boolean isMetadata(InetAddress address) { return "169.254.169.254".equals(address.getHostAddress()); }
    private boolean isIpv6UniqueLocal(InetAddress address) {
        byte[] bytes = address.getAddress();
        return bytes.length == 16 && ((bytes[0] & 0xFE) == 0xFC);
    }
}
