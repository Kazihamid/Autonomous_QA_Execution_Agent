package com.brac.automation.platform.application;

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
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications")
public class ApplicationController {
    private final ApplicationService service;
    public ApplicationController(ApplicationService service){this.service=service;}
    @GetMapping public List<ApplicationDtos.Response> list(@PathVariable UUID workspaceId){return service.list(workspaceId);}
    @PostMapping @ResponseStatus(HttpStatus.CREATED) public ApplicationDtos.Response create(@PathVariable UUID workspaceId,@Valid @RequestBody ApplicationDtos.CreateRequest request){return service.create(workspaceId,request);}
    @GetMapping("/{applicationId}") public ApplicationDtos.Response get(@PathVariable UUID workspaceId,@PathVariable UUID applicationId){return service.get(workspaceId,applicationId);}
    @PutMapping("/{applicationId}") public ApplicationDtos.Response update(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@Valid @RequestBody ApplicationDtos.UpdateRequest request){return service.update(workspaceId,applicationId,request);}
    @DeleteMapping("/{applicationId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable UUID workspaceId,@PathVariable UUID applicationId){service.delete(workspaceId,applicationId);}
}
