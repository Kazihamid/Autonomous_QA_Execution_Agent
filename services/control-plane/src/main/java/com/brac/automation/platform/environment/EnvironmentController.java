package com.brac.automation.platform.environment;

import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications/{applicationId}")
public class EnvironmentController {
    private final EnvironmentService service;
    public EnvironmentController(EnvironmentService service){this.service=service;}

    @GetMapping("/environments") public List<EnvironmentDtos.Response> list(@PathVariable UUID workspaceId,@PathVariable UUID applicationId){return service.list(workspaceId,applicationId);}
    @PostMapping("/environments") @ResponseStatus(HttpStatus.CREATED)
    public EnvironmentDtos.Response create(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@Valid @RequestBody EnvironmentDtos.CreateRequest request){return service.create(workspaceId,applicationId,request);}
    @PutMapping("/environments/{environmentId}")
    public EnvironmentDtos.Response update(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID environmentId,@Valid @RequestBody EnvironmentDtos.UpdateRequest request){return service.update(workspaceId,applicationId,environmentId,request);}
    @DeleteMapping("/environments/{environmentId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID environmentId){service.delete(workspaceId,applicationId,environmentId);}
    @PostMapping("/target-validation")
    public EnvironmentDtos.TargetValidationResponse validateTarget(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@Valid @RequestBody EnvironmentDtos.TargetValidationRequest request){return service.validateTarget(workspaceId,applicationId,request.url());}
}
