package com.brac.automation.platform.security;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class DevProfileGuardTest {
    @Test
    void allowsLocal() {
        assertDoesNotThrow(() -> DevProfileGuard.check("local"));
        assertDoesNotThrow(() -> DevProfileGuard.check(" LOCAL "));
    }

    @Test
    void rejectsEverythingElse() {
        assertThrows(IllegalStateException.class, () -> DevProfileGuard.check(null));
        assertThrows(IllegalStateException.class, () -> DevProfileGuard.check(""));
        assertThrows(IllegalStateException.class, () -> DevProfileGuard.check("production"));
    }
}
