package com.brac.automation.platform.codegen;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Component
public class CodeGeneratorClient {
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final String baseUrl;
    public CodeGeneratorClient(ObjectMapper mapper, @Value("${platform.code-generator.base-url}") String baseUrl) {
        this.mapper=mapper; this.baseUrl=baseUrl.replaceAll("/+$","");
        this.http=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).build();
    }
    public JsonNode generate(JsonNode request) {
        try {
            String body=mapper.writeValueAsString(request);
            HttpRequest req=HttpRequest.newBuilder(URI.create(baseUrl+"/api/v1/generate")).version(HttpClient.Version.HTTP_1_1).timeout(Duration.ofSeconds(60))
                .header("Content-Type","application/json").header("Accept","application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build();
            HttpResponse<String> res=http.send(req,HttpResponse.BodyHandlers.ofString());
            if(res.statusCode()<200||res.statusCode()>=300) throw new CodeGeneratorException("Code Generator HTTP "+res.statusCode()+": "+res.body());
            return mapper.readTree(res.body());
        } catch (CodeGeneratorException ex) { throw ex; }
        catch (Exception ex) { if (ex instanceof InterruptedException) Thread.currentThread().interrupt(); throw new CodeGeneratorException("Code Generator request failed: "+ex.getMessage(),ex); }
    }
}
