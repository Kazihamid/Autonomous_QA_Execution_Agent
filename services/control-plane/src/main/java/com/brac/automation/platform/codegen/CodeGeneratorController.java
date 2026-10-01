package com.brac.automation.platform.codegen;
import jakarta.validation.Valid;import java.util.List;import java.util.UUID;import org.springframework.http.*;import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/workspaces/{workspaceId}/applications/{applicationId}/scenarios/{scenarioId}/implementations")
public class CodeGeneratorController {
 private final CodeGeneratorService service; public CodeGeneratorController(CodeGeneratorService service){this.service=service;}
 @PostMapping @ResponseStatus(HttpStatus.CREATED) public CodeGeneratorDtos.ImplementationDetail generate(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID scenarioId,@Valid @RequestBody CodeGeneratorDtos.GenerateRequest request){return service.generate(workspaceId,applicationId,scenarioId,request);}
 @GetMapping public List<CodeGeneratorDtos.ImplementationSummary> list(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID scenarioId){return service.list(workspaceId,applicationId,scenarioId);}
 @GetMapping("/{implementationId}") public CodeGeneratorDtos.ImplementationDetail get(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID scenarioId,@PathVariable UUID implementationId){return service.get(workspaceId,applicationId,scenarioId,implementationId);}
 @GetMapping(value="/{implementationId}/download",produces="application/zip") public ResponseEntity<byte[]> download(@PathVariable UUID workspaceId,@PathVariable UUID applicationId,@PathVariable UUID scenarioId,@PathVariable UUID implementationId){byte[] data=service.zip(workspaceId,applicationId,scenarioId,implementationId);return ResponseEntity.ok().header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=automation-implementation-"+implementationId+".zip").contentType(MediaType.parseMediaType("application/zip")).body(data);}
}
