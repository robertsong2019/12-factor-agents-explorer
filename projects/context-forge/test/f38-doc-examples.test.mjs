import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { generateDocExamples, formatDocExamples } from '../context-forge.mjs';

describe('generateDocExamples', () => {
  it('returns all four file types with content', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.agentsMd, 'should have agentsMd');
    assert.ok(ex.cursorRules, 'should have cursorRules');
    assert.ok(ex.copilotInstructions, 'should have copilotInstructions');
    assert.ok(ex.claudeMd, 'should have claudeMd');
    
    // Each should be non-empty markdown
    for (const [key, val] of Object.entries({ agentsMd: ex.agentsMd, cursorRules: ex.cursorRules, copilotInstructions: ex.copilotInstructions, claudeMd: ex.claudeMd })) {
      assert.ok(val.length > 50, `${key} should be substantial (>50 chars), got ${val.length}`);
    }
  });

  it('includes stats object with line counts', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.stats, 'should have stats');
    assert.equal(typeof ex.stats.agentsMdLines, 'number');
    assert.equal(typeof ex.stats.cursorRulesLines, 'number');
    assert.equal(typeof ex.stats.copilotInstructionsLines, 'number');
    assert.equal(typeof ex.stats.claudeMdLines, 'number');
    assert.equal(typeof ex.stats.totalOutput, 'number');
    assert.ok(ex.stats.totalOutput > 0, 'totalOutput should be positive');
  });

  it('agentsMd contains mock project data', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.agentsMd.includes('my-app'), 'should contain project name');
    assert.ok(ex.agentsMd.includes('JavaScript'), 'should contain language');
    assert.ok(ex.agentsMd.includes('Express'), 'should contain framework');
  });

  it('cursorRules contains coding guidance', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.cursorRules.includes('my-app'), 'should reference project name');
    assert.ok(/test/i.test(ex.cursorRules), 'should mention testing');
  });

  it('copilotInstructions contains project context', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.copilotInstructions.includes('my-app'), 'should contain project name');
    assert.ok(ex.copilotInstructions.includes('Guidelines'), 'should have guidelines section');
  });

  it('supports excluding git info', () => {
    const ex = generateDocExamples({ includeGitInfo: false });
    
    assert.ok(!ex.agentsMd.includes('## Git Activity'), 'should not have Git Activity when includeGitInfo=false');
  });

  it('supports including git info (default)', () => {
    const ex = generateDocExamples();
    
    assert.ok(ex.agentsMd.includes('## Git Activity'), 'should have Git Activity by default');
    assert.ok(ex.agentsMd.includes('Alice'), 'should contain contributor name');
    assert.ok(ex.agentsMd.includes('342'), 'should contain commit count');
  });

  it('stats line counts match actual content', () => {
    const ex = generateDocExamples();
    
    assert.equal(ex.stats.agentsMdLines, ex.agentsMd.split('\n').length);
    assert.equal(ex.stats.cursorRulesLines, ex.cursorRules.split('\n').length);
    assert.equal(ex.stats.claudeMdLines, ex.claudeMd.split('\n').length);
  });
});

describe('formatDocExamples', () => {
  it('produces a combined markdown document', () => {
    const ex = generateDocExamples();
    const formatted = formatDocExamples(ex);
    
    assert.ok(formatted.includes('# 📖 Context-Forge Documentation Examples'));
    assert.ok(formatted.includes('## AGENTS.md Example'));
    assert.ok(formatted.includes('## .cursorrules Example'));
    assert.ok(formatted.includes('## CLAUDE.md Example'));
    assert.ok(formatted.includes('## Statistics'));
  });

  it('wraps outputs in code blocks', () => {
    const ex = generateDocExamples();
    const formatted = formatDocExamples(ex);
    
    assert.ok(formatted.includes('```markdown'), 'should wrap in markdown code blocks');
  });

  it('includes stats table', () => {
    const ex = generateDocExamples();
    const formatted = formatDocExamples(ex);
    
    assert.ok(formatted.includes('| File | Lines |'));
    assert.ok(formatted.includes('AGENTS.md'));
    assert.ok(formatted.includes('.cursorrules'));
  });

  it('handles empty examples gracefully', () => {
    const mockEx = {
      agentsMd: '',
      cursorRules: '',
      copilotInstructions: '',
      claudeMd: '',
      stats: { agentsMdLines: 0, cursorRulesLines: 0, copilotInstructionsLines: 0, claudeMdLines: 0, totalOutput: 0 },
    };

    const formatted = formatDocExamples(mockEx);
    assert.ok(formatted.length > 50, 'should still produce a valid document');
  });
});
