package com.brac.automation.platform.environment;

import com.brac.automation.platform.common.PolicyViolationException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class EnvironmentTargetValidatorTest {
    private EnvironmentTargetValidator validator(boolean allowPrivate) {
        TargetPolicyProperties p=new TargetPolicyProperties();p.setAllowPrivateTargets(allowPrivate);return new EnvironmentTargetValidator(p);
    }
    @Test void rejectsFileScheme(){assertThrows(PolicyViolationException.class,()->validator(false).validate("file:///etc/passwd"));}
    @Test void rejectsLocalhost(){assertThrows(PolicyViolationException.class,()->validator(false).validate("http://localhost:8080"));}
    @Test void rejectsMetadata(){assertThrows(PolicyViolationException.class,()->validator(false).validate("http://169.254.169.254/latest/meta-data"));}
    @Test void acceptsUnresolvablePublicStyleHostAsUnverified(){TargetValidationResult r=validator(false).validate("https://qa.example.invalid");assertTrue(r.valid());assertFalse(r.dnsResolved());}
}
