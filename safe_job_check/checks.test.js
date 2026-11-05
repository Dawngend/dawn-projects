const test = require("node:test");
const assert = require("node:assert/strict");
const { checks, checkJobPost } = require("./checks");

const riskySamples = [
  {
    name: "Personal email address",
    text: "For an interview, email recruiting.manager@gmail.com with your resume.",
  },
  {
    name: "Interview only through a messaging app",
    text: "Your interview will be conducted only on Telegram.",
  },
  {
    name: "Request for money, fees, or purchases",
    text: "Pay a $75 training fee before starting your new remote position.",
  },
  {
    name: "Request for money, fees, or purchases",
    text: "Buy two iTunes gift cards for office supplies and send us the codes.",
  },
  {
    name: "Request for money, fees, or purchases",
    text: "Send the refundable deposit in Bitcoin to the hiring manager's wallet.",
  },
  {
    name: "Early request for personal or financial details",
    text: "Reply with your SSN and bank account number before we arrange an interview.",
  },
  {
    name: "Unrealistic pay or effortless income",
    text: "Earn $5,000 per week from home doing easy work with no experience needed.",
  },
  {
    name: "Urgency or pressure",
    text: "Apply now today because there are limited spots. Start immediately.",
  },
  {
    name: "Vague company or role",
    text: "The company name is confidential and the duties will be discussed later.",
  },
  {
    name: "Cheque or payment forwarding",
    text: "We will send you a cheque to deposit, then buy equipment from our vendor.",
  },
  {
    name: "Cheque or payment forwarding",
    text: "Receive customer payments into your account and forward the balance to us.",
  },
  {
    name: "Poor grammar paired with a personal-information request",
    text: "We is hiring. Need you send your bank account number for verify payroll.",
  },
];

test("the rules cover the nine warning signs and include clear guidance", () => {
  assert.equal(checks.length, 9);

  for (const check of checks) {
    assert.equal(typeof check.name, "string");
    assert.ok(check.name.length > 0);
    assert.equal(typeof check.test, "function");
    assert.equal(typeof check.why, "string");
    assert.ok(check.why.length > 0);
    assert.equal(typeof check.whatToDo, "string");
    assert.ok(check.whatToDo.length > 0);
  }
});

for (const sample of riskySamples) {
  test(`detects ${sample.name}`, () => {
    const check = checks.find((candidate) => candidate.name === sample.name);
    assert.equal(check.test(sample.text), true);
    assert.ok(checkJobPost(sample.text).some((warning) => warning.name === sample.name));
  });
}

test("a clean job post has no warnings", () => {
  const text = `
    Senior software engineer at Example Health. We are hiring through our official
    careers page. The role involves designing and maintaining healthcare software
    with our engineering team. The salary range is $140,000 to $175,000 per year.
    Apply at examplehealth.com/careers. Selected candidates will meet the team for
    two interviews. Email careers@examplehealth.com with questions about the role.
  `;

  assert.deepEqual(checkJobPost(text), []);
});

test("a risky job post reports all nine warning signs", () => {
  const text = `
    Your interview will be conducted only on Telegram. Apply now today because
    there are limited spots. The company name is confidential and the duties will
    be discussed later. Pay a $75 training fee and buy iTunes gift cards. We will
    send you a cheque to deposit and buy equipment. Reply with your SSN and bank
    account number. We is hiring. Need you send your bank account number for verify
    payroll. Earn $5,000 per week from home doing easy work. Email hiring@gmail.com.
  `;
  const warnings = checkJobPost(text);

  assert.deepEqual(
    warnings.map((warning) => warning.name),
    checks.map((check) => check.name),
  );
  assert.deepEqual(
    warnings,
    checks.map(({ name, why, whatToDo }) => ({ name, why, whatToDo })),
  );
});

test("empty and non-string input has no warnings", () => {
  assert.deepEqual(checkJobPost(""), []);
  assert.deepEqual(checkJobPost(null), []);
  assert.deepEqual(checkJobPost(undefined), []);
  assert.deepEqual(checkJobPost({ text: "Send Bitcoin" }), []);
});
