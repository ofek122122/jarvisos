//! The tool registry — DATA, not code (BRIEF-phase2 §2). Loaded from
//! TOML; every tool declares its capability level, args schema and
//! timeout. jv-act's copy of this file is AUTHORITATIVE: whatever the
//! brain claims in intent.action is re-derived here and mismatches are
//! rejected.

use std::collections::BTreeMap;

use serde::Deserialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Capability {
    Observe,
    Benign,
    Destructive,
    Privileged,
}

impl Capability {
    pub fn as_str(self) -> &'static str {
        match self {
            Capability::Observe => "observe",
            Capability::Benign => "benign",
            Capability::Destructive => "destructive",
            Capability::Privileged => "privileged",
        }
    }

    /// The confirmation rule is structural, not per-tool: destructive
    /// and privileged ALWAYS confirm. No TOML field can waive it.
    pub fn needs_confirmation(self) -> bool {
        self >= Capability::Destructive
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ArgType {
    String,
    Number,
    Integer,
    Boolean,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ArgSpec {
    #[serde(rename = "type")]
    pub arg_type: ArgType,
    #[serde(default)]
    pub required: bool,
    #[serde(default)]
    pub description: String,
    /// Optional closed set of allowed string values.
    #[serde(default)]
    pub one_of: Option<Vec<String>>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ToolSpec {
    pub name: String,
    pub description: String,
    pub capability: Capability,
    #[serde(default = "default_timeout_ms")]
    pub timeout_ms: u64,
    #[serde(default)]
    pub args: BTreeMap<String, ArgSpec>,
}

fn default_timeout_ms() -> u64 {
    10_000
}

#[derive(Debug, Deserialize)]
struct RegistryFile {
    #[serde(rename = "tool")]
    tools: Vec<ToolSpec>,
}

#[derive(Debug, Clone)]
pub struct Registry {
    tools: BTreeMap<String, ToolSpec>,
}

impl Registry {
    pub fn from_toml(text: &str) -> anyhow::Result<Self> {
        let file: RegistryFile = toml::from_str(text)?;
        let mut tools = BTreeMap::new();
        for t in file.tools {
            anyhow::ensure!(
                tools.insert(t.name.clone(), t).is_none(),
                "duplicate tool in registry"
            );
        }
        Ok(Self { tools })
    }

    pub fn get(&self, name: &str) -> Option<&ToolSpec> {
        self.tools.get(name)
    }

    pub fn tools(&self) -> impl Iterator<Item = &ToolSpec> {
        self.tools.values()
    }

    /// Validate args against the tool's spec: required present, types
    /// match, no unknown keys, one_of respected.
    pub fn validate_args(spec: &ToolSpec, args: &serde_json::Value) -> Result<(), String> {
        let obj = args.as_object().ok_or("args must be an object")?;
        for (name, aspec) in &spec.args {
            match obj.get(name) {
                None if aspec.required => return Err(format!("missing required arg '{name}'")),
                None => {}
                Some(v) => {
                    let ok = match aspec.arg_type {
                        ArgType::String => v.is_string(),
                        ArgType::Number => v.is_number(),
                        ArgType::Integer => v.is_i64() || v.is_u64(),
                        ArgType::Boolean => v.is_boolean(),
                    };
                    if !ok {
                        return Err(format!("arg '{name}' has wrong type"));
                    }
                    if let (Some(allowed), Some(s)) = (&aspec.one_of, v.as_str()) {
                        if !allowed.iter().any(|a| a == s) {
                            return Err(format!("arg '{name}' must be one of {allowed:?}"));
                        }
                    }
                }
            }
        }
        for key in obj.keys() {
            if !spec.args.contains_key(key) {
                return Err(format!("unknown arg '{key}'"));
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const TOML: &str = r#"
        [[tool]]
        name = "file.search"
        description = "find files"
        capability = "observe"
        [tool.args.pattern]
        type = "string"
        required = true
        [tool.args.content]
        type = "boolean"

        [[tool]]
        name = "trash.empty"
        description = "empty the trash"
        capability = "destructive"
    "#;

    #[test]
    fn parses_and_derives_confirmation() {
        let reg = Registry::from_toml(TOML).unwrap();
        assert!(!reg.get("file.search").unwrap().capability.needs_confirmation());
        assert!(reg.get("trash.empty").unwrap().capability.needs_confirmation());
        assert!(reg.get("nope").is_none());
    }

    #[test]
    fn arg_validation() {
        let reg = Registry::from_toml(TOML).unwrap();
        let spec = reg.get("file.search").unwrap();
        let ok = serde_json::json!({"pattern": "*.rs", "content": true});
        assert!(Registry::validate_args(spec, &ok).is_ok());
        let missing = serde_json::json!({});
        assert!(Registry::validate_args(spec, &missing).unwrap_err().contains("pattern"));
        let wrong = serde_json::json!({"pattern": 7});
        assert!(Registry::validate_args(spec, &wrong).unwrap_err().contains("wrong type"));
        let unknown = serde_json::json!({"pattern": "x", "bogus": 1});
        assert!(Registry::validate_args(spec, &unknown).unwrap_err().contains("unknown"));
    }
}
