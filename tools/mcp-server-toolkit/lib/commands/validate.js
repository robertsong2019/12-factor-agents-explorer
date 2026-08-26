import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import yaml from 'js-yaml';
import Validator from 'jsonschema';

const TRANSPORTS = ['stdio', 'sse', 'stdlib'];
const NAME_RE = /^[a-z0-9][a-z0-9_-]*$/;

export function validateConfig(config) {
  // Returns { errors: [{path, message}], summary: {...} }
  const errors = [];
  const push = (p, m) => errors.push({ path: p, message: m });

  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    return { errors: [{ path: '$', message: '配置必须是对象' }], summary: {} };
  }

  // name
  if (!config.name) {
    push('name', '缺少必填字段 name');
  } else if (typeof config.name !== 'string' || !NAME_RE.test(config.name)) {
    push('name', `无效名称 "${config.name}"：仅允许小写字母、数字、连字符、下划线，且以字母或数字开头`);
  }

  // version
  if (!config.version) {
    push('version', '缺少必填字段 version');
  } else if (!/^\d+\.\d+\.\d+(-[\w.]+)?$/.test(String(config.version))) {
    push('version', `无效版本 "${config.version}"：应为 semver 格式（如 1.0.0）`);
  }

  // transport
  if (!config.transport) {
    push('transport', '缺少必填字段 transport');
  } else if (!TRANSPORTS.includes(config.transport)) {
    push('transport', `无效传输类型 "${config.transport}"：只能是 ${TRANSPORTS.join(' | ')}`);
  }

  // tools
  const tools = Array.isArray(config.tools) ? config.tools : [];
  if (config.tools !== undefined && !Array.isArray(config.tools)) {
    push('tools', 'tools 必须是数组');
  }
  const toolNames = new Map();
  for (const [i, tool] of tools.entries()) {
    const p = `tools[${i}]`;
    if (!tool || typeof tool !== 'object') {
      push(p, '工具必须是对象');
      continue;
    }
    if (!tool.name) {
      push(`${p}.name`, '缺少必填字段 name');
    } else if (!/^[a-zA-Z_][\w-]*$/.test(tool.name)) {
      push(`${p}.name`, `无效工具名 "${tool.name}"：须以字母或下划线开头`);
    } else if (toolNames.has(tool.name)) {
      push(`${p}.name`, `重复的工具名 "${tool.name}"（首次出现在 tools[${toolNames.get(tool.name)}]）`);
    } else {
      toolNames.set(tool.name, i);
    }
    if (tool.inputSchema !== undefined) {
      if (typeof tool.inputSchema !== 'object' || Array.isArray(tool.inputSchema)) {
        push(`${p}.inputSchema`, 'inputSchema 必须是 JSON Schema 对象');
      } else if (tool.inputSchema.type && tool.inputSchema.type !== 'object') {
        push(`${p}.inputSchema`, `inputSchema.type 应为 "object"，实际为 "${tool.inputSchema.type}"（MCP 工具参数必须是对象）`);
      }
    }
  }

  // resources
  const resources = Array.isArray(config.resources) ? config.resources : [];
  if (config.resources !== undefined && !Array.isArray(config.resources)) {
    push('resources', 'resources 必须是数组');
  }
  for (const [i, res] of resources.entries()) {
    const p = `resources[${i}]`;
    if (!res || typeof res !== 'object') {
      push(p, '资源必须是对象');
      continue;
    }
    if (!res.uri) {
      push(`${p}.uri`, '缺少必填字段 uri');
    } else if (!/^[\w-]+:\/\//.test(res.uri) && !res.uri.startsWith('/')) {
      push(`${p}.uri`, `无效 URI "${res.uri}"：应以 scheme:// 或 / 开头`);
    }
  }

  // prompts
  const prompts = Array.isArray(config.prompts) ? config.prompts : [];
  if (config.prompts !== undefined && !Array.isArray(config.prompts)) {
    push('prompts', 'prompts 必须是数组');
  }
  const promptNames = new Map();
  for (const [i, prompt] of prompts.entries()) {
    const p = `prompts[${i}]`;
    if (!prompt || typeof prompt !== 'object') {
      push(p, '提示模板必须是对象');
      continue;
    }
    if (!prompt.name) {
      push(`${p}.name`, '缺少必填字段 name');
    } else if (promptNames.has(prompt.name)) {
      push(`${p}.name`, `重复的提示模板名 "${prompt.name}"（首次出现在 prompts[${promptNames.get(prompt.name)}]）`);
    } else {
      promptNames.set(prompt.name, i);
    }
  }

  return {
    errors,
    summary: {
      tools: tools.length,
      resources: resources.length,
      prompts: prompts.length,
      transport: config.transport,
    },
  };
}

export async function validate(configPath, options) {
  const target = configPath || 'mcp-server.json';

  if (!(await fs.pathExists(target))) {
    console.log(chalk.red(`❌ 配置文件不存在: ${target}`));
    process.exit(1);
  }

  const raw = await fs.readFile(target, 'utf8');
  let config;
  const ext = path.extname(target).toLowerCase();

  if (ext === '.yaml' || ext === '.yml') {
    try {
      config = yaml.load(raw);
    } catch (e) {
      console.log(chalk.red(`❌ YAML 解析失败: ${e.message}`));
      process.exit(1);
    }
  } else {
    try {
      config = JSON.parse(raw);
    } catch (e) {
      console.log(chalk.red(`❌ JSON 解析失败: ${e.message}`));
      process.exit(1);
    }
  }

  // Custom schema validation (--schema)
  if (options && options.schema) {
    if (!(await fs.pathExists(options.schema))) {
      console.log(chalk.red(`❌ schema 文件不存在: ${options.schema}`));
      process.exit(1);
    }
    let schema;
    try {
      schema = JSON.parse(await fs.readFile(options.schema, 'utf8'));
    } catch (e) {
      console.log(chalk.red(`❌ schema JSON 解析失败: ${e.message}`));
      process.exit(1);
    }
    const result = new Validator.Validator().validate(config, schema);
    if (!result.valid) {
      console.log(chalk.red(`\n❌ ${target} 未通过自定义 schema 校验 (${result.errors.length} 处错误):\n`));
      for (const err of result.errors) {
        console.log(chalk.yellow(`  ${err.property || err.path || '$'}: ${err.message}`));
      }
      process.exit(1);
    }
    console.log(chalk.green(`✅ ${target} 通过自定义 schema 校验`));
  }

  const { errors, summary } = validateConfig(config);

  console.log(chalk.cyan(`\n🔍 校验 ${target}\n`));

  if (errors.length > 0) {
    console.log(chalk.red(`❌ 发现 ${errors.length} 处错误:\n`));
    for (const e of errors) {
      console.log(chalk.yellow(`  ${e.path}: ${e.message}`));
    }
    process.exit(1);
  }

  console.log(chalk.green('✅ 配置有效\n'));
  console.log(chalk.white(`  transport: ${summary.transport}`));
  console.log(chalk.white(`  tools:     ${summary.tools}`));
  console.log(chalk.white(`  resources: ${summary.resources}`));
  console.log(chalk.white(`  prompts:   ${summary.prompts}\n`));
}
