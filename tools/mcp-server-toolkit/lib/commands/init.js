import fs from 'fs-extra';
import path from 'path';
import inquirer from 'inquirer';
import chalk from 'chalk';
import ora from 'ora';

export async function init(name, options) {
  console.log(chalk.cyan('🚀 MCP Server 项目初始化\n'));

  // 如果没有提供名称，询问用户
  if (!name) {
    const answers = await inquirer.prompt([
      {
        type: 'input',
        name: 'name',
        message: '项目名称:',
        default: 'my-mcp-server',
        validate: (input) => {
          if (!input) return '项目名称不能为空';
          if (!/^[a-z0-9-]+$/.test(input)) {
            return '项目名称只能包含小写字母、数字和连字符';
          }
          return true;
        }
      },
      {
        type: 'input',
        name: 'description',
        message: '项目描述:',
        default: 'A custom MCP server'
      },
      {
        type: 'list',
        name: 'type',
        message: '传输类型:',
        choices: [
          { name: 'stdio (标准输入输出)', value: 'stdio' },
          { name: 'SSE (Server-Sent Events)', value: 'sse' },
          { name: 'stdlib (标准库)', value: 'stdlib' }
        ],
        default: 'stdio'
      },
      {
        type: 'confirm',
        name: 'addExample',
        message: '是否添加示例代码?',
        default: true
      }
    ]);

    name = answers.name;
    options.type = answers.type;
    options.description = answers.description;
    options.addExample = answers.addExample;
  }

  // CLI 提供的名称走同一校验（与交互式 inquirer validate 一致）
  if (name && !/^[a-z0-9-]+$/.test(name)) {
    console.log(chalk.red('❌ 项目名称只能包含小写字母、数字和连字符'));
    process.exit(1);
  }

  const projectDir = path.resolve(name);

  // 检查目录是否已存在
  if (await fs.pathExists(projectDir)) {
    console.log(chalk.red(`❌ 目录 ${name} 已存在`));
    process.exit(1);
  }

  const spinner = ora('创建项目结构...').start();

  try {
    // 创建目录结构
    await fs.ensureDir(projectDir);
    await fs.ensureDir(path.join(projectDir, 'src'));
    await fs.ensureDir(path.join(projectDir, 'test'));
    await fs.ensureDir(path.join(projectDir, 'examples'));

    // 创建 package.json
    const packageJson = {
      name: name,
      version: '1.0.0',
      description: options.description || 'A custom MCP server',
      type: 'module',
      main: 'dist/index.js',
      bin: {
        [name]: './dist/index.js'
      },
      scripts: {
        build: 'tsc',
        dev: 'tsc --watch',
        test: 'jest',
        start: `node dist/index.js`
      },
      keywords: ['mcp', 'server', 'model-context-protocol'],
      author: '',
      license: 'MIT',
      dependencies: {
        '@modelcontextprotocol/sdk': '^1.0.0'
      },
      devDependencies: {
        '@types/node': '^20.0.0',
        'typescript': '^5.0.0',
        jest: '^29.0.0',
        '@types/jest': '^29.0.0'
      },
      engines: {
        node: '>=18.0.0'
      }
    };

    await fs.writeJson(path.join(projectDir, 'package.json'), packageJson, { spaces: 2 });

    // 创建 TypeScript 配置
    const tsConfig = {
      compilerOptions: {
        target: 'ES2020',
        module: 'ES2020',
        lib: ['ES2020'],
        outDir: './dist',
        rootDir: './src',
        strict: true,
        esModuleInterop: true,
        skipLibCheck: true,
        forceConsistentCasingInFileNames: true,
        moduleResolution: 'node',
        resolveJsonModule: true,
        declaration: true,
        declarationMap: true,
        sourceMap: true
      },
      include: ['src/**/*'],
      exclude: ['node_modules', 'dist', 'test']
    };

    await fs.writeJson(path.join(projectDir, 'tsconfig.json'), tsConfig, { spaces: 2 });

    // 创建 MCP 服务器配置文件
    const mcpConfig = {
      name: name,
      version: '1.0.0',
      description: options.description || 'A custom MCP server',
      transport: options.type || 'stdio',
      capabilities: {
        resources: {},
        tools: {},
        prompts: {}
      },
      resources: [],
      tools: [],
      prompts: []
    };

    await fs.writeJson(path.join(projectDir, 'mcp-server.json'), mcpConfig, { spaces: 2 });

    // 创建主服务器文件
    const serverCode = generateServerCode(name, options.type, options.addExample || options.example);
    await fs.writeFile(path.join(projectDir, 'src/index.ts'), serverCode);

    // 创建 README
    const readme = generateReadme(name, options);
    await fs.writeFile(path.join(projectDir, 'README.md'), readme);

    // 创建 .gitignore
    const gitignore = `node_modules/
dist/
.DS_Store
*.log
.env
`;
    await fs.writeFile(path.join(projectDir, '.gitignore'), gitignore);

    spinner.succeed(chalk.green('✅ 项目创建成功!'));

    console.log(chalk.cyan('\n📦 下一步:\n'));
    console.log(chalk.white(`  cd ${name}`));
    console.log(chalk.white('  npm install'));
    console.log(chalk.white('  npm run build'));
    console.log(chalk.white('  npm start\n'));

    console.log(chalk.yellow('💡 提示: 编辑 src/index.ts 和 mcp-server.json 来定制你的 MCP 服务器\n'));

  } catch (error) {
    spinner.fail(chalk.red('❌ 项目创建失败'));
    console.error(error);
    process.exit(1);
  }
}

function generateServerCode(name, transportType, addExample) {
  const imports = `import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
`;

  const serverSetup = `
// 创建 MCP 服务器实例
const server = new Server(
  {
    name: '${name}',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
      resources: {},
      prompts: {},
    },
  }
);
`;

  let handlers = '';

  if (addExample) {
    // 添加示例工具处理器
    handlers += `
// 示例工具: echo
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'echo',
        description: '回显输入的文本',
        inputSchema: {
          type: 'object',
          properties: {
            text: {
              type: 'string',
              description: '要回显的文本',
            },
          },
          required: ['text'],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === 'echo') {
    return {
      content: [
        {
          type: 'text',
          text: \`Echo: \${args.text}\`,
        },
      ],
    };
  }

  throw new Error(\`Unknown tool: \${name}\`);
});
`;
  } else {
    // 空处理器
    handlers += `
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: [] };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name } = request.params;
  throw new Error(\`Unknown tool: \${name}\`);
});
`;
  }

  // 资源处理器
  handlers += `
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return { resources: [] };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;
  throw new Error(\`Unknown resource: \${uri}\`);
});

// 提示模板处理器
server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return { prompts: [] };
});

server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name } = request.params;
  throw new Error(\`Unknown prompt: \${name}\`);
});
`;

  const serverStart = `
// 启动服务器
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('${name} MCP server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error in main():', error);
  process.exit(1);
});
`;

  return imports + serverSetup + handlers + serverStart;
}

function generateReadme(name, options) {
  return `# ${name}

${options.description || 'A custom MCP server'}

## 概述

这是一个使用 Model Context Protocol (MCP) 构建的服务器。

## 安装

\`\`\`bash
npm install
\`\`\`

## 构建

\`\`\`bash
npm run build
\`\`\`

## 运行

\`\`\`bash
npm start
\`\`\`

## 配置

编辑 \`mcp-server.json\` 文件来配置服务器的资源和工具。

## 开发

\`\`\`bash
npm run dev
\`\`\`

## 测试

\`\`\`bash
npm test
\`\`\`

## MCP 协议

这个服务器实现了 [Model Context Protocol](https://modelcontextprotocol.io/)，支持:

- **工具 (Tools)**: 可被客户端调用的函数
- **资源 (Resources)**: 服务器提供的数据资源
- **提示模板 (Prompts)**: 预定义的提示模板

## 许可证

MIT
`;
}
