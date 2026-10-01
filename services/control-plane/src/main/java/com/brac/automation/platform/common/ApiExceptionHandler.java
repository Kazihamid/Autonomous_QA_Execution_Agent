package com.brac.automation.platform.common;

import com.brac.automation.platform.codegen.CodeGeneratorException;

import com.brac.automation.platform.recorder.RecorderWorkerException;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    ResponseEntity<Map<String, Object>> notFound(ResourceNotFoundException ex) {
        return error(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", ex.getMessage());
    }

    @ExceptionHandler(ConflictException.class)
    ResponseEntity<Map<String, Object>> conflict(ConflictException ex) {
        return error(HttpStatus.CONFLICT, "CONFLICT", ex.getMessage());
    }

    @ExceptionHandler(PolicyViolationException.class)
    ResponseEntity<Map<String, Object>> policy(PolicyViolationException ex) {
        return error(HttpStatus.UNPROCESSABLE_ENTITY, "TARGET_POLICY_VIOLATION", ex.getMessage());
    }

    @ExceptionHandler(AccessDeniedException.class)
    ResponseEntity<Map<String, Object>> forbidden(AccessDeniedException ex) {
        return error(HttpStatus.FORBIDDEN, "FORBIDDEN", "You are not authorized to perform this operation.");
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<Map<String, Object>> invalid(MethodArgumentNotValidException ex) {
        String details = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .collect(Collectors.joining("; "));
        return error(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", details);
    }

    @ExceptionHandler(RecorderWorkerException.class)
    ResponseEntity<Map<String, Object>> recorderUnavailable(RecorderWorkerException ex) {
        return error(HttpStatus.BAD_GATEWAY, "RECORDER_WORKER_ERROR", ex.getMessage());
    }

    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<Map<String, Object>> badRequest(IllegalArgumentException ex) {
        return error(HttpStatus.BAD_REQUEST, "BAD_REQUEST", ex.getMessage());
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus status, String code, String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("timestamp", Instant.now().toString());
        body.put("status", status.value());
        body.put("code", code);
        body.put("message", message);
        return ResponseEntity.status(status).body(body);
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(CodeGeneratorException.class)
    public org.springframework.http.ResponseEntity<java.util.Map<String,Object>> codeGenerator(CodeGeneratorException ex) {
        return org.springframework.http.ResponseEntity.status(org.springframework.http.HttpStatus.BAD_GATEWAY).body(java.util.Map.of("message", ex.getMessage(), "code", "CODE_GENERATOR_ERROR"));
    }
}
