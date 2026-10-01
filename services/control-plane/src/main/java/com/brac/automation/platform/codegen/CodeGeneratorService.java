package com.brac.automation.platform.codegen;

import com.brac.automation.platform.application.ApplicationService;
import com.brac.automation.platform.audit.AuditService;
import com.brac.automation.platform.common.ResourceNotFoundException;
import com.brac.automation.platform.recorder.ScenarioVersionEntity;
import com.brac.automation.platform.recorder.ScenarioVersionRepository;
import com.brac.automation.platform.recorder.TestScenarioEntity;
import com.brac.automation.platform.recorder.TestScenarioRepository;
import com.brac.automation.platform.security.CurrentUserService;
import com.brac.automation.platform.workspace.WorkspaceAccessGuard;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class CodeGeneratorService {
 private static final String GENERATOR_VERSION="0.3.2";
 private static final java.util.Set<String> TARGETS=java.util.Set.of("PLAYWRIGHT_PYTEST","SELENIUM_TESTNG");
 private final AutomationImplementationRepository implementations; private final TestScenarioRepository scenarios; private final ScenarioVersionRepository versions;
 private final ApplicationService applications; private final WorkspaceAccessGuard guard; private final CurrentUserService currentUser; private final AuditService audit; private final CodeGeneratorClient client; private final ObjectMapper mapper;
 public CodeGeneratorService(AutomationImplementationRepository implementations,TestScenarioRepository scenarios,ScenarioVersionRepository versions,ApplicationService applications,WorkspaceAccessGuard guard,CurrentUserService currentUser,AuditService audit,CodeGeneratorClient client,ObjectMapper mapper){this.implementations=implementations;this.scenarios=scenarios;this.versions=versions;this.applications=applications;this.guard=guard;this.currentUser=currentUser;this.audit=audit;this.client=client;this.mapper=mapper;}
 @Transactional
 public CodeGeneratorDtos.ImplementationDetail generate(UUID workspaceId,UUID applicationId,UUID scenarioId,CodeGeneratorDtos.GenerateRequest request){
   guard.requireWrite(workspaceId); applications.entity(workspaceId,applicationId); TestScenarioEntity scenario=scenario(workspaceId,applicationId,scenarioId); ScenarioVersionEntity version=latest(scenarioId);
   String target=request.target().trim().toUpperCase(); if(!TARGETS.contains(target)) throw new IllegalArgumentException("Unsupported target profile. Use PLAYWRIGHT_PYTEST or SELENIUM_TESTNG.");
   JsonNode ir=parse(version.getAutomationIr()); var payload=mapper.createObjectNode(); payload.put("scenarioId",scenarioId.toString()); payload.put("scenarioVersionId",version.getId().toString()); payload.put("scenarioVersion",version.getVersionNo()); payload.put("target",target); payload.set("automationIr",ir); payload.put("generatorVersion",GENERATOR_VERSION); payload.set("configuration",mapper.createObjectNode());
   audit.success(workspaceId,"CODE_GENERATION_REQUESTED","TEST_SCENARIO",scenarioId,Map.of("target",target,"scenarioVersion",version.getVersionNo()));
   JsonNode out=client.generate(payload); int implVersion=(int)implementations.countByScenarioVersionIdAndTargetProfile(version.getId(),target)+1;
   AutomationImplementationEntity entity=implementations.save(new AutomationImplementationEntity(workspaceId,applicationId,scenarioId,version.getId(),implVersion,target,out.path("generatorVersion").asText(GENERATOR_VERSION),out.path("status").asText("GENERATED"),out.path("irCanonicalHash").asText(),out.path("sourceHash").asText(),out.path("files").toString(),out.path("sourceMap").toString(),out.path("validation").toString(),currentUser.currentUser().getId()));
   audit.success(workspaceId,"CODE_GENERATION_COMPLETED","AUTOMATION_IMPLEMENTATION",entity.getId(),Map.of("target",target,"sourceHash",entity.getSourceHash(),"implementationVersion",implVersion)); return detail(entity);
 }
 @Transactional(readOnly=true) public List<CodeGeneratorDtos.ImplementationSummary> list(UUID workspaceId,UUID applicationId,UUID scenarioId){guard.requireRead(workspaceId);applications.entity(workspaceId,applicationId);scenario(workspaceId,applicationId,scenarioId);return implementations.findByWorkspaceIdAndApplicationIdAndScenarioIdOrderByCreatedAtDesc(workspaceId,applicationId,scenarioId).stream().map(this::summary).toList();}
 @Transactional(readOnly=true) public CodeGeneratorDtos.ImplementationDetail get(UUID workspaceId,UUID applicationId,UUID scenarioId,UUID implementationId){guard.requireRead(workspaceId);applications.entity(workspaceId,applicationId);return detail(entity(workspaceId,applicationId,scenarioId,implementationId));}
 @Transactional(readOnly=true) public byte[] zip(UUID workspaceId,UUID applicationId,UUID scenarioId,UUID implementationId){guard.requireRead(workspaceId);applications.entity(workspaceId,applicationId);AutomationImplementationEntity e=entity(workspaceId,applicationId,scenarioId,implementationId);try{List<CodeGeneratorDtos.GeneratedFile> files=mapper.readValue(e.getFilesJson(),new TypeReference<List<CodeGeneratorDtos.GeneratedFile>>(){});ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(ZipOutputStream zip=new ZipOutputStream(bytes,StandardCharsets.UTF_8)){for(var f:files){String safe=safePath(f.path());zip.putNextEntry(new ZipEntry(safe));zip.write(f.content().getBytes(StandardCharsets.UTF_8));zip.closeEntry();}}return bytes.toByteArray();}catch(Exception ex){throw new CodeGeneratorException("Could not build implementation ZIP: "+ex.getMessage(),ex);}}
 private String safePath(String value){String p=value.replace('\\','/');if(p.startsWith("/")||p.contains("../"))throw new CodeGeneratorException("Unsafe generated path: "+value);return p;}
 private TestScenarioEntity scenario(UUID w,UUID a,UUID s){return scenarios.findByIdAndWorkspaceIdAndApplicationId(s,w,a).orElseThrow(()->new ResourceNotFoundException("Scenario not found."));}
 private ScenarioVersionEntity latest(UUID s){return versions.findFirstByScenarioIdOrderByVersionNoDesc(s).orElseThrow(()->new ResourceNotFoundException("Scenario version not found."));}
 private AutomationImplementationEntity entity(UUID w,UUID a,UUID s,UUID id){return implementations.findByIdAndWorkspaceIdAndApplicationIdAndScenarioId(id,w,a,s).orElseThrow(()->new ResourceNotFoundException("Automation implementation not found."));}
 private CodeGeneratorDtos.ImplementationSummary summary(AutomationImplementationEntity e){return new CodeGeneratorDtos.ImplementationSummary(e.getId(),e.getTargetProfile(),e.getImplementationVersion(),e.getGeneratorVersion(),e.getStatus(),e.getSourceHash(),e.getCreatedAt());}
 private CodeGeneratorDtos.ImplementationDetail detail(AutomationImplementationEntity e){try{List<CodeGeneratorDtos.GeneratedFile> files=mapper.readValue(e.getFilesJson(),new TypeReference<List<CodeGeneratorDtos.GeneratedFile>>(){});return new CodeGeneratorDtos.ImplementationDetail(summary(e),e.getScenarioVersionId(),e.getIrCanonicalHash(),files,parse(e.getSourceMapJson()),parse(e.getValidationJson()));}catch(Exception ex){throw new CodeGeneratorException("Could not read generated implementation: "+ex.getMessage(),ex);}}
 private JsonNode parse(String s){return mapper.readTree(s);}
}
