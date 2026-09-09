// F84: analyzer branch coverage — 5 uncovered branches found via
// --experimental-test-coverage on 2026-09-10 (cycle: 2576-2691 main() excluded
// as CLI-entry; these are the largest non-main uncovered blocks):
//   6456-6464  analyzeAsyncPatterns   unhandled-rejection look-ahead
//   8539-8548  analyzeCodeSmells      arrow >=5 params
//   10223-10238 analyzeGuardClauses   if/else-wraps-body guard opportunity
//   10396-10404 analyzeParameterObjects trailing optional params
//   11087-11098 analyzeReturnPaths     unreachable code after return (same line)
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  analyzeAsyncPatterns,
  analyzeCodeSmells,
  analyzeGuardClauses,
  analyzeParameterObjects,
  analyzeReturnPaths,
} from "../context-forge.mjs";

describe("F84: analyzeAsyncPatterns unhandled-rejection branch", () => {
  it("flags .then( chain with no .catch within look-ahead window", () => {
    const files = [{
      path: "a.js",
      content: `function loadData() {
  fetch(url).then(res => res.json());
  const x = 1;
}`,
    }];
    const result = analyzeAsyncPatterns(files);
    assert.ok(result.totalUnhandledRejections >= 1, "should count unhandled rejections");
    const issue = result.files[0].issues.find(i => i.type === "unhandled_rejection");
    assert.ok(issue, "should detect unhandled .then rejection");
    assert.equal(issue.severity, "high");
  });

  it("does not flag .then( when .catch follows within look-ahead window", () => {
    const files = [{
      path: "a.js",
      content: `function loadData() {
  fetch(url)
    .then(res => res.json())
    .catch(handleError);
}`,
    }];
    const result = analyzeAsyncPatterns(files);
    assert.equal(result.totalUnhandledRejections, 0, "chained .catch should suppress the issue");
  });
});

describe("F84: analyzeCodeSmells arrow >=5 params branch", () => {
  it("flags arrow function with 6 parameters", () => {
    const files = [{
      path: "a.js",
      content: `const compute = (a, b, c, d, e, f) => a + b + c + d + e + f;\n`,
    }];
    const result = analyzeCodeSmells(files);
    assert.ok(result.summary.tooManyParams >= 1, "should count too-many-params");
    const issue = result.files[0].issues.find(i => /Too many parameters in arrow/.test(i.description));
    assert.ok(issue, "should emit too-many-params issue");
    assert.match(issue.description, /6$/);
  });

  it("does not flag arrow function with 3 parameters", () => {
    const files = [{
      path: "a.js",
      content: `const add = (a, b, c) => a + b + c;\n`,
    }];
    const result = analyzeCodeSmells(files);
    assert.equal(result.summary.tooManyParams, 0);
  });
});

describe("F84: analyzeGuardClauses if/else-wraps-body branch", () => {
  it("flags function whose body is one if/else with else-block at end", () => {
    const content = `function processOrder(order) {
  if (order.valid) {
    const total = order.items.reduce((sum, item) => sum + item.price * item.qty, 0);
    const tax = total * 0.08;
    const shipping = total > 100 ? 0 : 10;
    const grand = total + tax + shipping;
    const receipt = { id: order.id, total, tax, shipping, grand };
    saveReceipt(receipt);
    notifyCustomer(order.email, receipt);
    auditLog(order.id, grand);
    return receipt;
  }
  else { return null; }
}`;
    const files = [{ path: "a.js", content }];
    const result = analyzeGuardClauses(files);
    const issue = result.issues.find(i => i.label === "Guard clause opportunity");
    assert.ok(issue, "should detect guard clause opportunity");
    assert.equal(issue.severity, "medium");
  });

  it("does not flag short functions with if/else", () => {
    const content = `function pick(x) {
  if (x > 0) {
    return x;
  }
  else { return -x; }
}`;
    const files = [{ path: "a.js", content }];
    const result = analyzeGuardClauses(files);
    const issue = result.issues.find(i => i.label === "Guard clause opportunity");
    assert.equal(issue, undefined, "small body should not trigger");
  });
});

describe("F84: analyzeParameterObjects trailing-optional branch", () => {
  it("flags function with 3 trailing optional params", () => {
    const files = [{
      path: "a.js",
      content: `function createUser(name, role = "user", active = true, tags = []) {
  return { name, role, active, tags };
}`,
    }];
    const result = analyzeParameterObjects(files);
    const issue = result.issues.find(i => i.label === "Many optional parameters");
    assert.ok(issue, "should detect many-optional-params");
    assert.equal(issue.severity, "low");
  });

  it("does not flag function with only required params", () => {
    const files = [{
      path: "a.js",
      content: `function createUser(name, role, active, tags) {
  return { name, role, active, tags };
}`,
    }];
    const result = analyzeParameterObjects(files);
    const issue = result.issues.find(i => i.label === "Many optional parameters");
    assert.equal(issue, undefined);
  });
});

describe("F84: analyzeReturnPaths unreachable-after-return branch", () => {
  it("flags same-line code after return statement", () => {
    const files = [{
      path: "a.js",
      content: `function f() {
  return g(); h();
}`,
    }];
    const result = analyzeReturnPaths(files);
    assert.ok(result.stats.unreachableCodeCount >= 1, "should count unreachable");
    const issue = result.issues.find(i => i.type === "unreachable_code");
    assert.ok(issue, "should emit unreachable_code");
    assert.equal(issue.funcName, "f");
  });

  it("does not flag early-return guard on its own line", () => {
    const files = [{
      path: "a.js",
      content: `function f(x) {
  if (!x) return;
  console.log(x);
}`,
    }];
    const result = analyzeReturnPaths(files);
    assert.equal(result.stats.unreachableCodeCount, 0, "guard clause is NOT unreachable");
  });
});
