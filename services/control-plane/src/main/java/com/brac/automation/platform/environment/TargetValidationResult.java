package com.brac.automation.platform.environment;
import java.util.List;
public record TargetValidationResult(boolean valid, boolean dnsResolved, List<String> resolvedAddresses, List<String> warnings) {}
