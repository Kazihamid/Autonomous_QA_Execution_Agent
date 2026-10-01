package com.brac.automation.platform.environment;

import java.util.ArrayList;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix="platform.target-policy")
public class TargetPolicyProperties {
    private boolean allowPrivateTargets = false;
    private List<String> allowedHosts = new ArrayList<>();
    public boolean isAllowPrivateTargets(){return allowPrivateTargets;}
    public void setAllowPrivateTargets(boolean allowPrivateTargets){this.allowPrivateTargets=allowPrivateTargets;}
    public List<String> getAllowedHosts(){return allowedHosts;}
    public void setAllowedHosts(List<String> allowedHosts){this.allowedHosts=allowedHosts==null?new ArrayList<>():allowedHosts;}
}
