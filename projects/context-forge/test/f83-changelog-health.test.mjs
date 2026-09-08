import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeChangelogHealth, formatChangelogHealthReport } from '../context-forge.mjs';

const KEEP_A_CHANGELOG = `# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.2.0] - 2024-06-15

### Added
- New export API

### Fixed
- Cache invalidation bug

## [1.1.0] - 2024-03-01

### Added
- Watch mode

## [1.0.0] - 2024-01-15

### Added
- Initial release

### Security
- Hardened input validation
`;

describe('F83: analyzeChangelogHealth()', () => {
  describe('basic functionality', () => {
    it('returns correct structure', () => {
      const result = analyzeChangelogHealth({ path: 'CHANGELOG.md', content: KEEP_A_CHANGELOG });
      assert.ok(typeof result.found === 'boolean');
      assert.ok(typeof result.score === 'number');
      assert.ok(typeof result.grade === 'string');
      assert.ok(result.versions);
      assert.ok(Array.isArray(result.issues));
      assert.ok(result.stats);
    });

    it('handles null input', () => {
      const result = analyzeChangelogHealth(null);
      assert.equal(result.found, false);
      assert.equal(result.score, 0);
      assert.equal(result.grade, 'F');
      assert.ok(result.issues.some((i) => i.severity === 'critical'));
    });

    it('handles undefined input', () => {
      const result = analyzeChangelogHealth();
      assert.equal(result.found, false);
      assert.equal(result.grade, 'F');
    });

    it('handles null content', () => {
      const result = analyzeChangelogHealth({ path: 'CHANGELOG.md', content: null });
      assert.equal(result.found, false);
      assert.equal(result.grade, 'F');
    });

    it('handles empty content', () => {
      const result = analyzeChangelogHealth({ path: 'CHANGELOG.md', content: '' });
      assert.equal(result.found, true);
      assert.equal(result.stats.releases, 0);
      assert.equal(result.grade, 'F');
    });
  });

  describe('version heading parsing', () => {
    it('parses bracket semver headings [1.2.0] - date', () => {
      const result = analyzeChangelogHealth({ content: '## [1.2.0] - 2024-06-15\n- fix' });
      assert.equal(result.stats.releases, 1);
      assert.equal(result.versions.latest, '1.2.0');
    });

    it('parses bare semver headings 1.2.0', () => {
      const result = analyzeChangelogHealth({ content: '## 1.2.0\n- fix' });
      assert.equal(result.stats.releases, 1);
      assert.equal(result.versions.latest, '1.2.0');
    });

    it('parses v-prefixed headings v1.2.0', () => {
      const result = analyzeChangelogHealth({ content: '## v1.2.0 - 2024-06-15\n- fix' });
      assert.equal(result.versions.latest, '1.2.0');
    });

    it('parses parenthesised dates 1.2.0 (2024-06-15)', () => {
      const result = analyzeChangelogHealth({ content: '## 1.2.0 (2024-06-15)\n- fix' });
      assert.equal(result.stats.releases, 1);
      assert.equal(result.versions.latestValidDate, '2024-06-15');
    });

    it('counts Unreleased as a section but not as latest release', () => {
      const result = analyzeChangelogHealth({ content: '## [Unreleased]\n\n## [1.0.0] - 2024-01-01\n- init' });
      assert.equal(result.stats.releases, 1);
      assert.equal(result.versions.latest, '1.0.0');
      assert.equal(result.versions.unreleasedSection, true);
    });

    it('flags invalid semver versions', () => {
      const result = analyzeChangelogHealth({ content: '## [beta] - 2024-01-01\n- x' });
      assert.equal(result.versions.count, 1);
      assert.equal(result.versions.latestIsValidSemVer, false);
      assert.ok(result.issues.some((i) => /invalid semver/i.test(i.message)));
    });

    it('flags two-component versions as invalid semver', () => {
      const result = analyzeChangelogHealth({ content: '## [1.2] - 2024-01-01\n- x' });
      assert.equal(result.versions.latestIsValidSemVer, false);
    });

    it('flags missing version headings', () => {
      const result = analyzeChangelogHealth({ content: 'Just some random notes without headings.' });
      assert.equal(result.stats.releases, 0);
      assert.ok(result.issues.some((i) => i.severity === 'high' && /no version heading/i.test(i.message)));
    });
  });

  describe('ordering', () => {
    it('detects descending order', () => {
      const result = analyzeChangelogHealth({ content: KEEP_A_CHANGELOG });
      assert.equal(result.versions.inDescendingOrder, true);
    });

    it('detects out-of-order versions', () => {
      const content = '## [1.0.0] - 2024-06-01\n- a\n\n## [1.2.0] - 2024-01-01\n- b';
      const result = analyzeChangelogHealth({ content });
      assert.equal(result.versions.inDescendingOrder, false);
      assert.ok(result.issues.some((i) => /descending|older.*newer|order/i.test(i.message)));
    });

    it('compares semver properly (1.10.0 > 1.9.0)', () => {
      const content = '## [1.10.0] - 2024-06-01\n- a\n\n## [1.9.0] - 2024-01-01\n- b';
      const result = analyzeChangelogHealth({ content });
      assert.equal(result.versions.inDescendingOrder, true);
    });
  });

  describe('dates', () => {
    it('flags versions without dates', () => {
      const result = analyzeChangelogHealth({ content: '## [1.0.0]\n- x\n\n## [0.9.0] - 2024-01-01\n- y' });
      assert.equal(result.versions.versionsWithoutDate, 1);
      assert.ok(result.issues.some((i) => /without.*date|missing.*date/i.test(i.message)));
    });

    it('does not require a date for Unreleased', () => {
      const result = analyzeChangelogHealth({ content: '## [Unreleased]\n\n## [1.0.0] - 2024-01-01\n- x' });
      assert.equal(result.versions.versionsWithoutDate, 0);
    });

    it('rejects non-ISO date formats', () => {
      const result = analyzeChangelogHealth({ content: '## [1.0.0] - June 15, 2024\n- x' });
      assert.equal(result.versions.isoDateFormats, false);
      assert.ok(result.issues.some((i) => /iso/i.test(i.message)));
    });

    it('accepts ISO date format YYYY-MM-DD', () => {
      const result = analyzeChangelogHealth({ content: '## [1.0.0] - 2024-06-15\n- x' });
      assert.equal(result.versions.isoDateFormats, true);
    });
  });

  describe('Keep a Changelog sections', () => {
    it('detects standard sections', () => {
      const result = analyzeChangelogHealth({ content: KEEP_A_CHANGELOG });
      assert.equal(result.sections.added, true);
      assert.equal(result.sections.fixed, true);
      assert.equal(result.sections.security, true);
      assert.equal(result.sections.changed, false);
    });

    it('matches section headings case-insensitively', () => {
      const result = analyzeChangelogHealth({ content: '## [1.0.0] - 2024-01-01\n\n### ADDED\n- x' });
      assert.equal(result.sections.added, true);
    });

    it('scores higher with more standard sections', () => {
      const withSections = analyzeChangelogHealth({ content: KEEP_A_CHANGELOG });
      const bare = analyzeChangelogHealth({ content: '## [1.2.0] - 2024-06-15\n- fix\n\n## [1.1.0] - 2024-03-01\n- feat\n\n## [1.0.0] - 2024-01-15\n- init' });
      assert.ok(withSections.score > bare.score);
    });
  });

  describe('empty releases and placeholders', () => {
    it('detects empty releases', () => {
      const content = '## [1.1.0] - 2024-06-01\n\n## [1.0.0] - 2024-01-01\n- real content here';
      const result = analyzeChangelogHealth({ content });
      assert.equal(result.versions.emptyReleases, 1);
      assert.ok(result.issues.some((i) => /empty release/i.test(i.message)));
    });

    it('treats whitespace-only body as empty', () => {
      const content = '## [1.1.0] - 2024-06-01\n   \n\n## [1.0.0] - 2024-01-01\n- real content';
      const result = analyzeChangelogHealth({ content });
      assert.equal(result.versions.emptyReleases, 1);
    });

    it('detects placeholder content', () => {
      const result = analyzeChangelogHealth({ content: '## [1.0.0] - 2024-01-01\n- TODO: write changelog' });
      assert.ok(result.issues.some((i) => /placeholder/i.test(i.message)));
    });
  });

  describe('scoring and grading', () => {
    it('grades an exemplary changelog as A or B', () => {
      const result = analyzeChangelogHealth({ content: KEEP_A_CHANGELOG });
      assert.ok(['A', 'B'].includes(result.grade), `expected A or B, got ${result.grade} (${result.score})`);
    });

    it('clamps score to 0-100', () => {
      const result = analyzeChangelogHealth({ content: '## [weird] - not a date\n\n\n\n## [junk]\nTODO' });
      assert.ok(result.score >= 0 && result.score <= 100);
    });

    it('missing file scores 0', () => {
      const result = analyzeChangelogHealth(null);
      assert.equal(result.score, 0);
    });
  });
});

describe('F83: formatChangelogHealthReport()', () => {
  it('returns No data string for falsy result', () => {
    const report = formatChangelogHealthReport(null);
    assert.match(report, /No data/i);
  });

  it('reports missing file', () => {
    const report = formatChangelogHealthReport(analyzeChangelogHealth(null));
    assert.match(report, /No CHANGELOG file found/i);
  });

  it('renders grade, latest version and stats for a healthy changelog', () => {
    const report = formatChangelogHealthReport(analyzeChangelogHealth({ content: KEEP_A_CHANGELOG }));
    assert.match(report, /## Changelog Health Analysis/);
    assert.match(report, /\*\*Grade:\*\*/);
    assert.match(report, /1\.2\.0/);
    assert.match(report, /✅/);
  });

  it('lists issues with severity markers', () => {
    const report = formatChangelogHealthReport(
      analyzeChangelogHealth({ content: '## [1.0.0]\n- x' }),
    );
    assert.match(report, /### Issues/);
    assert.match(report, /🟠|🟡|🔵/);
  });

  it('renders Unreleased flag', () => {
    const report = formatChangelogHealthReport(analyzeChangelogHealth({ content: KEEP_A_CHANGELOG }));
    assert.match(report, /Unreleased/);
  });
});
