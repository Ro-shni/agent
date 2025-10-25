import yaml
from typing import List, Dict, Any

# =================== K8S PARSING HELPERS ===================

def parse_mcp_events_format(mcp_response: str) -> List[Dict[str, Any]]:
    """Parse MCP's custom event format with correct field extraction"""
    if not mcp_response or not isinstance(mcp_response, str):
        return []
    
    events = []
    
    # MCP returns events in a custom format
    if "The following events (YAML format) were found:" in mcp_response:
        content = mcp_response.replace("The following events (YAML format) were found:", "").strip()
        
        # Split by "\n- InvolvedObject:" to get individual events
        event_blocks = content.split('\n- InvolvedObject:')
        
        for i, block in enumerate(event_blocks):
            if not block.strip():
                continue
            
            # Add back the "InvolvedObject:" prefix
            if i > 0 or not block.startswith('InvolvedObject:'):
                block = 'InvolvedObject:' + block
            
            # Parse the event block
            event = {}
            involved_object = {}
            
            lines = block.split('\n')
            current_section = None
            j = 0
            
            while j < len(lines):
                line = lines[j]
                stripped = line.strip()
                
                if not stripped:
                    j += 1
                    continue
                
                indent = len(line) - len(line.lstrip())
                
                if ':' in stripped:
                    colon_idx = stripped.index(':')
                    key = stripped[:colon_idx].strip()
                    value = stripped[colon_idx+1:].strip()
                    
                    # Remove quotes
                    if value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    elif value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    
                    # Root level fields
                    if indent <= 2:
                        if key == "InvolvedObject":
                            current_section = "involvedObject"
                            event["involvedObject"] = {}
                        elif key == "Namespace":
                            event["namespace"] = value
                        elif key == "Message":
                            # Handle multi-line messages
                            message_lines = [value] if value else []
                            k = j + 1
                            while k < len(lines):
                                next_line = lines[k]
                                next_indent = len(next_line) - len(next_line.lstrip())
                                next_stripped = next_line.strip()
                                
                                if next_indent <= 2 and ':' in next_stripped:
                                    next_key = next_stripped.split(':')[0].strip()
                                    if next_key in ['Namespace', 'Message', 'Reason', 'Type', 'Timestamp']:
                                        break
                                
                                if next_stripped and next_indent > 2:
                                    message_lines.append(next_stripped)
                                k += 1
                            
                            event["message"] = ' '.join(message_lines)
                            j = k - 1
                        elif key == "Reason":
                            event["reason"] = value
                        elif key == "Type":
                            event["type"] = value
                        elif key == "Timestamp":
                            event["firstTimestamp"] = value
                            event["lastTimestamp"] = value
                    # InvolvedObject sub-fields
                    elif current_section == "involvedObject" and indent > 2:
                        if key == "Kind":
                            involved_object["kind"] = value
                        elif key == "Name":
                            involved_object["name"] = value
                        elif key == "Namespace":
                            involved_object["namespace"] = value
                            if not event.get("namespace"):
                                event["namespace"] = value
                
                j += 1
            
            if involved_object:
                event["involvedObject"] = involved_object
            
            if not event.get("namespace") and involved_object.get("namespace"):
                event["namespace"] = involved_object["namespace"]
            
            if event and ("involvedObject" in event or "message" in event):
                events.append(event)
    
    return events

def parse_k8s_yaml_output(yaml_text: str) -> List[Dict[str, Any]]:
    """Parse Kubernetes YAML output - handles both standard YAML and MCP event format"""
    if not yaml_text or not isinstance(yaml_text, str):
        return []
    
    # Check if it's MCP's custom event format
    if "The following events (YAML format) were found:" in yaml_text:
        return parse_mcp_events_format(yaml_text)
    
    # Try standard YAML parsing
    try:
        if '---' in yaml_text:
            documents = yaml_text.split('---')
            resources = []
            for doc in documents:
                if doc.strip():
                    parsed = yaml.safe_load(doc.strip())
                    if parsed:
                        if isinstance(parsed, list):
                            resources.extend(parsed)
                        else:
                            resources.append(parsed)
            return resources
        else:
            resources = yaml.safe_load(yaml_text)
            if isinstance(resources, list):
                return resources
            elif isinstance(resources, dict):
                if resources.get('kind') == 'List' and 'items' in resources:
                    return resources['items']
                return [resources]
            else:
                return []
    except yaml.YAMLError:
        return parse_mcp_events_format(yaml_text)