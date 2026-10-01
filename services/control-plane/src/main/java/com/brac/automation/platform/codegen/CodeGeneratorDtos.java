package com.brac.automation.platform.codegen;
import jakarta.validation.constraints.NotBlank;import java.time.Instant;import java.util.List;import java.util.Map;import java.util.UUID;import tools.jackson.databind.JsonNode;
public final class CodeGeneratorDtos {
 private CodeGeneratorDtos(){}
 public record GenerateRequest(@NotBlank String target){}
 public record ImplementationSummary(UUID id,String targetProfile,int implementationVersion,String generatorVersion,String status,String sourceHash,Instant createdAt){}
 public record GeneratedFile(String path,String content){}
 public record ImplementationDetail(ImplementationSummary implementation,UUID scenarioVersionId,String irCanonicalHash,List<GeneratedFile> files,JsonNode sourceMap,JsonNode validation){}
}
