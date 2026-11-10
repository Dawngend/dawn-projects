const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");
const { checks, checkJobPost } = require("./checks");

const samples = [
  {
    name: "Asks for money, fees or equipment purchases",
    risky: [
      "Pay a $75 training fee before starting your new position.",
      "You must buy equipment from our vendor before you can start.",
      "Send the refundable deposit in Bitcoin to the recruiter.",
      "Buy two iTunes gift cards and send us the codes.",
      "Buy Google Play cards and send us the codes.",
      "Please transfer money to us through Zelle to apply.",
      "An application fee is required to apply.",
    ],
    clean: [
      "We build Bitcoin wallets and cryptocurrency trading software.",
      "Design payment integrations for Zelle and gift cards.",
      "We pay for your training and purchase equipment for you.",
      "We cover all application fees and background check costs.",
      "You will receive an equipment stipend through payroll.",
      "No fees or equipment purchases are required.",
      "You do not need to buy equipment or pay any fees.",
      "Never send money or buy gift cards for a recruiter.",
      "We never ask candidates to send Bitcoin or transfer money.",
    ],
  },
  {
    name: "Asks for ID, bank or card details early",
    risky: [
      "Reply with your SSN and bank account number before we arrange an interview.",
      "Please upload a copy of your passport to apply.",
      "Send your debit card details to the recruiter.",
      "Provide your ID before the interview through our secure onboarding portal.",
    ],
    clean: [
      "Build bank account and credit card payment systems.",
      "A driver's license is needed to operate the delivery van.",
      "We never ask for your SSN or bank account number during interviews.",
      "Do not send your passport or bank details to recruiters.",
      "Provide your bank details through secure payroll after accepting a written offer.",
      "After you are hired, upload your ID through our secure onboarding portal.",
      "Please provide support for bank account integrations.",
    ],
  },
  {
    name: "Interview only over chat apps",
    risky: [
      "Your interview will be conducted only on Telegram.",
      "We conduct interviews exclusively through WhatsApp.",
      "The interview is text-only via Google Chat, with no video call.",
    ],
    clean: [
      "Build Telegram bots and WhatsApp integrations.",
      "We use Signal and Discord for team communication.",
      "Message the manager on Telegram to schedule a video interview.",
      "Interviews are available by video or WhatsApp, whichever you prefer.",
      "We never conduct interviews only on Telegram.",
      "Interviews are not only on WhatsApp but also available by phone.",
      "Only our team announcements use Telegram. Interviews are held by video.",
    ],
  },
  {
    name: "Free email address instead of a company address",
    risky: [
      "For an interview, email recruiting.manager@gmail.com with your resume.",
      "Apply at hiring@yahoo.com.",
      "Recruiter email: hiring@outlook.com",
      "hiring@gmail.com",
    ],
    clean: [
      "Apply by emailing careers@examplehealth.com.",
      "Experience supporting Gmail and Outlook is useful.",
      "Candidate email: applicant@gmail.com",
      "Applicant's email address is applicant@gmail.com",
      "Your email: applicant@gmail.com",
      "You may apply from your personal email, such as applicant@gmail.com.",
      "Do not contact hiring@gmail.com; use our official careers page.",
      "Email careers@gmail.company with questions.",
      "Email careers@gmail.com.example.org with questions.",
    ],
  },
  {
    name: "Pay that is far too high for the work",
    risky: [
      "Earn $5,000 per week doing easy work with no experience needed.",
      "Make $500 per hour for simple data entry tasks.",
      "For just a few minutes of work a day, earn $1,000 per day.",
    ],
    clean: [
      "Senior surgeon needed at $800 per day with ten years of experience.",
      "Expert consultant at $150 per hour for complex security audits.",
      "Earn $500 per week with no experience required; training is provided.",
      "Remote software engineer, $5,000 per week, requires distributed systems expertise.",
      "Guaranteed base pay plus commission for sales staff.",
      "We do not promise $5,000 per week for easy work.",
      "Entry-level analyst at $25 per hour. Senior consultant at $150 per hour.",
    ],
  },
  {
    name: "Urgency and pressure",
    risky: [
      "Act now to secure your job offer.",
      "Accept the offer within two hours or lose your place.",
      "Apply now, today only, because there are limited spots.",
      "Apply now today because there are limited spots. Start immediately.",
      "You must reply immediately or the offer will be withdrawn.",
    ],
    clean: [
      "Resolve urgent support tickets and handle customer pressure.",
      "Apply now through our careers page.",
      "We are hiring immediately; the start date is flexible.",
      "Please respond to customers within two hours during your shift.",
      "Applications close on November 30. Interviews take place next month.",
      "We do not pressure applicants to act now.",
    ],
  },
  {
    name: "Vague company or role",
    risky: [
      "Company name not provided. Start your online role with us.",
      "Job duties are unspecified; details will be shared after registration.",
      "The employer name is withheld until you sign up.",
      "The company name is confidential and the duties will be discussed later.",
      "Job duties are unspecified, including how you will help customers.",
    ],
    clean: [
      "Part-time receptionist at Example Health, scheduling appointments and greeting patients.",
      "No experience required for our cashier role; you will process sales at Example Store.",
      "Work from home as a support agent, answering customer questions for Example Health.",
      "We provide full company details and a written job description.",
      "Job details are available on the company careers page.",
      "You will help customers whose company details are not provided.",
    ],
  },
  {
    name: "Cheque or payment-forwarding tasks",
    risky: [
      "We will send you a check to deposit, then buy equipment from our vendor.",
      "Deposit a cheque into your personal bank account and send the remainder to our vendor.",
      "Receive customer payments in your personal account and forward them to our suppliers.",
      "Receive customer payments into your account and forward the balance to us.",
    ],
    clean: [
      "We reimburse approved equipment purchases through payroll after you are hired.",
      "Salary is paid by cheque every two weeks.",
      "We send you a check for your monthly salary.",
      "Accounts payable staff process payments through the company bank account.",
      "Do not deposit a cheque or forward money for an unverified recruiter.",
      "A background check is required before using company equipment.",
    ],
  },
  {
    name: "Poor grammar with a request for personal information",
    risky: [
      "We is glad to offer you the job. Kindly send your full personal information.",
      "You is selected; please provide your date of birth.",
      "This is inform you to send your passport copy before the interview.",
      "We is hiring. Need you send your bank account number for verify payroll.",
    ],
    clean: [
      "Kindly send your resume and phone number to our company email.",
      "Please provide your address due to the fact that this role requires local travel.",
      "Please provide your full personal information through the secure onboarding portal.",
      "We is happy to hear from you. Tell us about your experience.",
      "We is hiring a coordinator at our office address.",
      "We is hiring. Do not send your personal information.",
      "We is hiring. Engineers maintain our servers. Please provide your phone number.",
    ],
  },
];

test("the nine signs each have a name, text test and plain guidance", () => {
  assert.deepEqual(checks.map((check) => check.name), samples.map((sample) => sample.name));
  for (const check of checks) {
    assert.equal(typeof check.test, "function");
    assert.ok(check.why.trim().length > 0);
    assert.ok(check.whatToDo.trim().length > 0);
  }
});

for (const sample of samples) {
  for (const text of sample.risky) {
    test(`${sample.name}: detects ${text}`, () => {
      const check = checks.find((candidate) => candidate.name === sample.name);
      assert.equal(check.test(text), true);
      assert.ok(checkJobPost(text).some((warning) => warning.name === sample.name));
    });
  }
  for (const text of sample.clean) {
    test(`${sample.name}: ignores ${text}`, () => {
      const check = checks.find((candidate) => candidate.name === sample.name);
      assert.equal(check.test(text), false);
      assert.ok(!checkJobPost(text).some((warning) => warning.name === sample.name));
    });
  }
}

test("a detailed clean job post has no warnings", () => {
  const text = `
    Part-time support engineer at Example Health, working from home.
    Maintain Telegram and WhatsApp integrations and support bank account systems.
    We pay for training and provide company equipment. No experience required.
    Senior specialists earn $150 per hour for complex security audits.
    Apply through our careers page or email careers@examplehealth.com.
    Kindly send your resume and phone number. Interviews are held by video.
    After accepting a written offer, provide your bank details through secure payroll.
    We reimburse approved equipment purchases after you are hired.
  `;
  assert.deepEqual(checkJobPost(text), []);
});

test("a risky job post reports all nine signs with guidance", () => {
  const text = `
    Act now to secure your job offer. Contact hiring@gmail.com.
    Your interview is only on Telegram. Pay a $75 training fee before starting.
    We will send you a check to deposit for equipment. Reply with your SSN.
    Earn $5,000 per week doing easy work. Company name not provided.
    We is glad to offer you the job. Kindly send your personal information.
  `;
  assert.deepEqual(
    checkJobPost(text),
    checks.map(({ name, why, whatToDo }) => ({ name, why, whatToDo })),
  );
});

test("separate safe statements do not hide real requests", () => {
  for (const text of [
    "We never ask you to buy gift cards. Send Bitcoin to pay a training fee.",
    "We pay for training, but you must buy equipment before starting.",
    "Do not share your bank details with strangers. Send your SSN to apply.",
    "We never ask for bank details; however, please upload your passport before the interview.",
    "Candidate email: applicant@gmail.com, recruiter email: hiring@gmail.com.",
    "You will help customers whose company details are not provided, but our company name is withheld.",
  ]) {
    assert.ok(checkJobPost(text).length > 0, text);
  }
});

test("request detection handles wrapping, capitalization and repeated calls", () => {
  const text = "PLEASE SEND\nyour SSN\nto apply.";
  const first = checkJobPost(text);
  assert.equal(first[0].name, "Asks for ID, bank or card details early");
  assert.deepEqual(checkJobPost(text), first);
});

test("the rules also work as a plain browser script without CommonJS", () => {
  const browser = {};
  runInNewContext(readFileSync(require.resolve("./checks"), "utf8"), browser);
  assert.equal(browser.safeJobCheck.checks.length, 9);
  assert.equal(browser.safeJobCheck.checkJobPost("A support role at Example Health.").length, 0);
  const warnings = browser.safeJobCheck.checkJobPost("Please send your SSN to apply.");
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0].name, "Asks for ID, bank or card details early");
});

test("empty and non-string input has no warnings", () => {
  for (const text of ["", "   ", null, undefined, 123, { text: "Send Bitcoin" }]) {
    assert.deepEqual(checkJobPost(text), []);
  }
});

for (const [count, verdict, className] of [
  [0, "No warnings found", "fine"],
  [1, "Be careful", "careful"],
  [2, "Be careful", "careful"],
  [3, "High risk", "risk"],
]) {
  test(`${count} warnings display the verdict "${verdict}"`, () => {
    const html = readFileSync(`${__dirname}/index.html`, "utf8");
    const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
    const elements = {};
    const browser = {
      document: {
        getElementById(id) {
          if (!elements[id]) {
            elements[id] = {
              addEventListener() {},
              replaceChildren() {},
              appendChild() {},
            };
          }
          return elements[id];
        },
        createElement() {
          return { appendChild() {}, append() {} };
        },
        createTextNode(text) {
          return text;
        },
      },
    };
    runInNewContext(script, browser);
    const warnings = Array.from({ length: count }, () => ({
      name: "Warning sign",
      why: "Reason to look closer.",
      whatToDo: "Verify the employer independently.",
    }));
    browser.showResults(warnings);
    const warningCount = `${count} ${count === 1 ? "warning sign" : "warning signs"} found.`;
    assert.equal(elements.verdict.textContent, verdict);
    assert.equal(elements.verdict.className, className);
    assert.equal(elements["warning-count"].textContent, warningCount);
    assert.equal(elements["result-status"].textContent, `${verdict}. ${warningCount}`);
    assert.equal(elements["no-warnings"].hidden, count !== 0);
    assert.equal(elements.results.hidden, false);
  });
}
