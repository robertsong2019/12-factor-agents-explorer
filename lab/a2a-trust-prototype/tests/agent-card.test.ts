// tests/agent-card.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, exportJWK } from '../src/crypto.js';
import { signAgentCard, verifyAgentCard } from '../src/agent-card.js';
import type { AgentCard } from '../src/agent-card.js';

async function makeCard(): Promise<{ card: AgentCard; keyPair: Awaited<ReturnType<typeof generateKeyPair>> }> {
  const keyPair = await generateKeyPair();
  const pubJwk = await exportJWK(keyPair.publicKey);
  const card: AgentCard = {
    id: 'agent-001',
    name: 'TestAgent',
    description: 'A test agent',
    url: 'https://example.com/agent',
    skills: [{ id: 'sql', name: 'SQL Query', description: 'Run SQL queries' }],
    publicKeyJwk: pubJwk,
    signedAt: Date.now(),
  };
  return { card, keyPair };
}

describe('SignedAgentCard', () => {
  it('signs and verifies a card', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    assert.ok(signed.signature);
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, true);
  });

  it('detects tampered name', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    signed.name = 'EvilAgent';
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('detects tampered skills', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    signed.skills.push({ id: 'admin', name: 'Admin', description: 'Full access' });
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('detects tampered description', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    signed.description = 'Malicious agent';
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('detects tampered url', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    signed.url = 'https://evil.com';
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('detects tampered signedAt', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    signed.signedAt = Date.now() + 99999;
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('detects tampered publicKeyJwk', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    const otherKey = await generateKeyPair();
    signed.publicKeyJwk = await exportJWK(otherKey.publicKey);
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, false);
  });

  it('supports trust extensions', async () => {
    const keyPair = await generateKeyPair();
    const pubJwk = await exportJWK(keyPair.publicKey);
    const card: AgentCard = {
      id: 'agent-ext',
      name: 'ExtendedAgent',
      description: 'Agent with extensions',
      url: 'https://example.com/ext',
      skills: [],
      publicKeyJwk: pubJwk,
      signedAt: Date.now(),
      extensions: {
        trust: {
          requiredLevel: 'trusted',
          perSkillPolicies: { sql: 'neutral' },
        },
      },
    };
    const signed = await signAgentCard(card, keyPair.privateKey);
    assert.ok(signed.extensions?.trust);
    assert.equal(signed.extensions!.trust!.requiredLevel, 'trusted');
    const valid = await verifyAgentCard(signed, keyPair.publicKey);
    assert.equal(valid, true);
  });

  it('rejects wrong public key', async () => {
    const { card, keyPair } = await makeCard();
    const signed = await signAgentCard(card, keyPair.privateKey);
    const otherKey = await generateKeyPair();
    const valid = await verifyAgentCard(signed, otherKey.publicKey);
    assert.equal(valid, false);
  });
});
