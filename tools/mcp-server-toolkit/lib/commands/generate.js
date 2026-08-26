import fs from 'fs-extra';
import path from 'path';
import chalk from 'chalk';
import { validateConfig } from './validate.js';

function tsJson(value, indent = 6) {
  // JSON is (almost) valid TS object literal; reuse JSON.stringify
  const pad = ' '.repeat(indent);
  return JSON.stringify(value, null, 2)
    .split('\n')
    .map((l, i) => (i === 0 ? l : pad + l))
    .join('\n');
}

function generateServerCode(config) {
  const tools = Array.isArray(config.tools) ? config.tools : [];
  const resources = Array.isArray(config.resources) ? config.resources : [];
  const prompts = Array.isArray(config.prompts) ? config.prompts : [];

  const listTools = tsJson(tools.map((t) => ({
    name: t.name,
    description: t.description || `${t.name} 工具`,
    ...(t.inputSchema ? { inputSchema: t.inputSchema } : {}),
  })));

  const listResources = tsJson(resources.map((r) => ({
    uri: r.uri,
    name: r.name || r.uri,
    ...(r.mimeType ? { mimeType: r.mimeType } : {}),
    description: r.description || '',
  })));

  const listPrompts = tsJson(prompts.map((p) => ({
    name: p.name,
    description: p.description || `${p.name} 提示模板`,
    ...(Array.isArray(p.arguments) ? { arguments: p.arguments } : {}),
  })));

  return `// 由 mcpt generate 自动生成 — 来自 ${config.name} 的 mcp-server 配置
// 请勿直接编辑此文件；修改配置后重新生成
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const server = new Server(
  {
    name: '${config.name}',
    version: '${config.version}',
  },
  {
    capabilities: {
      tools: ${tools.length > 0 ? '{}' : 'undefined'},
      resources: ${resources.length > 0 ? '{}' : 'undefined'},
      prompts: ${prompts.length > 0 ? '{}' : 'undefined'},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: ${listTools},
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name } = request.params;
  throw new Error(\`Unknown tool: \${name} — 请在 src 中实现 \${name} 后重新生成\`);
});

server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: ${listResources},
}));

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;
  throw new Error(\`Unknown resource: \${uri} — 请在 src 中实现后重新生成\`);
});

server.setRequestHandler(ListPromptsRequestSchema, async () => ({
  prompts: ${listPrompts},
}));

server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name } = request.params;
  throw new Error(\`Unknown prompt: \${name} — 请在 src 中实现后重新生成\`);
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('${config.name} MCP server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error in main():', error);
  process.exit(1);
});
`;
}

export { generateServerCode };

export async function generate(options) {
  const configFile = (options && options.file) || 'mcp-server.json';
  const outDir = (options && options.output) || 'dist';

  if (!(await fs.pathExists(configFile))) {
    console.log(chalk.red(`❌ 配置文件不存在: ${configFile}`));
    process.exit(1);
  }

  const raw = await fs.readFile(configFile, 'utf8');
  let config;
  const ext = path.extname(configFile).toLowerCase();
  if (ext === '.yaml' || ext === '.yml') {
    const yaml = await import('js-yaml');
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

  const { errors, summary } = validateConfig(config);
  if (errors.length > 0) {
    console.log(chalk.red(`\n❌ 配置无效（${errors.length} 处错误），拒绝生成。先运行 mcpt validate 修复:\n`));
    for (const e of errors) {
      console.log(chalk.yellow(`  ${e.path}: ${e.message}`));
    }
    process.exit(1);
  }

  if (config.transport !== 'stdio') {
    console.log(chalk.red(`❌ 尚未支持为 transport=${config.transport} 生成代码 — 当前仅支持 stdio`));
    process.exit(1);
  }

  const outFile = path.join(outDir, 'index.ts');
  if (await fs.pathExists(outFile)) {
    console.log(chalk.red(`❌ 输出文件已存在: ${outFile}（删除后重试，防止覆盖手写实现）`));
    process.exit(1);
  }

  await fs.ensureDir(outDir);
  await fs.writeFile(outFile, generateServerCode(config));

  console.log(chalk.green(`✅ 生成 ${outFile}`));
  console.log(chalk.white(`  tools:     ${summary.tools}`));
  console.log(chalk.white(`  resources: ${summary.resources}`));
  console.log(chalk.white(`  prompts:   ${summary.prompts}`));
}
