function statements(text) {
  return text
    .replace(/[’‘]/g, "'")
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?;])\s+|\b(?:but|however)\b/i)
    .map((part) => part.trim())
    .filter(Boolean);
}

function hasAffirmativeMatch(text, pattern) {
  for (const match of text.matchAll(new RegExp(pattern.source, "gi"))) {
    const before = text.slice(0, match.index).split(/[,;.!?]|\b(?:and|but|however)\b/i).pop();
    const after = text.slice(match.index + match[0].length);
    const negated = /\b(?:never|do not|does not|will not|would not|must not|should not|don't|doesn't|won't|wouldn't|shouldn't|can't|cannot|avoid|beware of|not required to|not asked to)\b.{0,70}$/i.test(before);
    const noPayment = /\b(?:no|zero)\s+(?:fees?|payments?|purchases?|deposits?|money)\b/i.test(match[0]);
    const notRequired = /^\s+(?:(?:is|are|will be)\s+)?not\s+(?:required|requested|needed|necessary)/i.test(after);
    if (!negated && !noPayment && !notRequired) return true;
  }
  return false;
}

const sensitiveDetails = /\b(?:ssn|social security (?:number|no)|bank (?:account(?: number)?|details|routing)|routing number|(?:credit|debit) card (?:number|details)|driver'?s? licen[cs]e|passport(?: number| copy)?|(?:photo |government[- ]issued )?id|date of birth|mother'?s maiden name)\b/;
const personalDetails = new RegExp(`${sensitiveDetails.source}|\\b(?:address|phone number|personal details|personal information)\\b`, "i");

function requestsDetails(text, details) {
  const request = new RegExp(
    String.raw`\b(?:send|provide|submit|share|upload|email|supply|include|give|reply with)\s+(?:(?:us|me)\s+)?(?:(?:a|the)\s+(?:copy|photo|scan)\s+of\s+)?(?:(?:your|a|the|full|valid)\s+){0,3}(?:${details.source})`,
    "i",
  );
  return hasAffirmativeMatch(text, request);
}

function asksForMoney(text) {
  return statements(text).some((part) => {
    const employerPays = /\b(?:we|(?:the|your|our) (?:company|employer))\s+(?:will\s+)?(?:pay|cover|purchase|buy|provide|fund|reimburse)\b/i.test(part);
    const candidatePays = /\b(?:you|applicants?|candidates?)\s+(?:must|need to|have to|are required to)|\b(?:ask|require|expect)\s+you\s+to\b/i.test(part);
    if (employerPays && !candidatePays) return false;
    return hasAffirmativeMatch(
      part,
      /\b(?:pay|send|wire|transfer|buy|purchase|cover)\b.{0,70}?\b(?:money|fees?|deposit|equipment|supplies|materials|starter kit|gift cards?|itunes cards?|google play cards?|bitcoin|crypto(?:currency)?|ethereum|usdt|usdc)\b|\b(?:pay|send|wire|transfer)\s+(?:(?:us|me)\s+)?\$\s*\d|\b(?:application|training|registration|processing)\s+(?:fee|deposit|payment)\s+(?:is\s+)?(?:required|due)\b/,
    );
  });
}

function asksForEarlyDetails(text) {
  return statements(text).some((part) => {
    if (!requestsDetails(part, sensitiveDetails)) return false;
    const early = /\b(?:before\s+(?:(?:a|an|the|your|any)\s+)?(?:interview|offer|hiring)|to apply|with your application|during (?:the |your )?(?:application|interview))\b/i.test(part);
    const afterOffer = /\b(?:after|once|following)\b.{0,40}\b(?:hired|hiring|accept(?:ed|ing)? (?:a |the |your )?(?:written )?offer|offer (?:is )?(?:accepted|verified))\b/i.test(part);
    return early || !afterOffer;
  });
}

function chatOnlyInterview(text) {
  return statements(text).some((part) =>
    hasAffirmativeMatch(part, /\binterviews?\b/) &&
    /\b(?:telegram|whats\s*app|signal|discord|google chat|hangouts|chat[- ]only|text[- ]only)\b/i.test(part) &&
    !/\bnot only\b|\bto schedule\b/i.test(part) &&
    hasAffirmativeMatch(part, /\b(?:only|exclusively|text[- ]only|chat[- ]only|no (?:video|phone) (?:calls?|interviews?))\b/),
  );
}

function freeContactEmail(text) {
  const address = String.raw`[\w.+-]+@(?:gmail\.com|googlemail\.com|yahoo\.(?:com|co\.uk)|hotmail\.(?:com|co\.uk)|outlook\.com|live\.com|icloud\.com|aol\.com|protonmail\.com|proton\.me|mail\.com)\b(?!\.[\w-])`;
  const contact = new RegExp(
    String.raw`\b(?:email|contact|write to|apply|send (?:your |a )?(?:resume|cv|application) to|recruiter(?: email)?|hiring(?: manager| team)?(?: email)?)\s*(?:(?:us|me)\s+)?(?:(?:at|to|via|is)\s+)?[:=]?\s*${address}`,
    "i",
  );
  const candidateAddress = new RegExp(
    String.raw`\b(?:candidate'?s?|applicant'?s?|your|personal)\s+email(?: address)?\s*(?:[:=]|\bis\b)\s*${address}`,
    "gi",
  );
  return statements(text).some((part) => {
    const contactText = part.replace(candidateAddress, " ");
    return new RegExp(`^${address}[.!]?$`, "i").test(contactText) || hasAffirmativeMatch(contactText, contact);
  });
}

function unrealisticPay(text) {
  return statements(text).some((part) => {
    const effortless = /\b(?:no experience|no skills|little (?:work|effort)|few (?:minutes|hours)|simple (?:tasks|data entry)|easy (?:work|tasks|money))\b/i.test(part);
    if (!effortless) return false;
    for (const rate of part.matchAll(/\$\s*(\d[\d,]*(?:\.\d+)?)\s*(?:a|per|\/)\s*(hour|day|week|month)\b/gi)) {
      const amount = Number(rate[1].replace(/,/g, ""));
      const threshold = { hour: 100, day: 500, week: 3000, month: 12000 }[rate[2].toLowerCase()];
      if (amount >= threshold && hasAffirmativeMatch(part, new RegExp(rate[0].replace(/[.*+?^${}()|[\]\\]/g, "\\$&")))) return true;
    }
    return hasAffirmativeMatch(part, /\b(?:get rich quick|risk[- ]free income|unlimited earnings)\b/);
  });
}

function pressureToAct(text) {
  return statements(text).some((part) => hasAffirmativeMatch(
    part,
    /\bact now\b|\b(?:apply|accept(?: the offer)?|reply|respond)\b.{0,50}?\b(?:today only|today.{0,40}?limited (?:spots|positions)|right now|immediately or|within (?:\d+|one|two|three) (?:minutes?|hours?) (?:or|to secure))\b|\bonly (?:\d+|one|two|three) (?:minutes?|hours?) left to (?:apply|accept|reply)\b/,
  ));
}

function vagueRole(text) {
  const missingDetails = /\b(?:(?:company|employer|business)\s+(?:name|details|identity)|(?:job|role|position)\s+(?:details|duties|responsibilities|description)|duties|responsibilities)\s+(?:(?:is|are|will be)\s+)?(?:not (?:provided|specified|disclosed)|unspecified|withheld|confidential|(?:provided|discussed|shared) later)\b/gi;
  return statements(text).some((part) => {
    for (const match of part.matchAll(missingDetails)) {
      const before = part.slice(0, match.index);
      if (!/\b(?:customers?|clients?)(?:'s|'| whose| with)?\s*$/i.test(before)) return true;
    }
    return false;
  });
}

function chequeOrForwarding(text) {
  return statements(text).some((part) => {
    const personalAccount = /\byour (?:own |personal )?(?:bank )?account\b/i.test(part);
    const chequeTask = hasAffirmativeMatch(part, /\b(?:deposit|cash)\b.{0,40}?\bche(?:ck|que)\b|\bsend you (?:a |the )?che(?:ck|que)\b/);
    const chequeContext = /\b(?:equipment|supplies|vendor|forward|remainder|remaining)\b/i.test(part);
    const forwardTask = hasAffirmativeMatch(part, /\b(?:forward|transfer|send|wire)\b.{0,40}?\b(?:payments?|money|funds|remainder|balance|rest|them)\b/);
    return (chequeTask && (personalAccount || chequeContext)) || (personalAccount && forwardTask);
  });
}

function grammarWithPersonalRequest(text) {
  const parts = statements(text);
  const grammarError = /\b(?:we is|you is|he are|she are|this is inform you|in order to you)\b/i;
  return parts.some((part, index) => {
    if (!requestsDetails(part, personalDetails)) return false;
    return grammarError.test(part) || (index > 0 && parts[index - 1].length < 160 && grammarError.test(parts[index - 1]));
  });
}

const checks = [
  {
    name: "Asks for money, fees or equipment purchases",
    test: asksForMoney,
    why: "A request to pay for a job, training or equipment can leave you out of pocket. Gift cards and cryptocurrency are especially hard to recover.",
    whatToDo: "Do not pay or send money. Verify the offer using contact details from the employer's official website.",
  },
  {
    name: "Asks for ID, bank or card details early",
    test: asksForEarlyDetails,
    why: "A request for identity or banking details before a verified offer can expose you to fraud.",
    whatToDo: "Do not send these details during an informal application or chat. Use a secure payroll or onboarding process only after verifying a written offer.",
  },
  {
    name: "Interview only over chat apps",
    test: chatOnlyInterview,
    why: "An interview restricted to a chat app can make the recruiter harder to verify. Using a messaging app alone is not proof of a scam.",
    whatToDo: "Ask for a phone or video interview and confirm the role through the employer's official careers site or company email.",
  },
  {
    name: "Free email address instead of a company address",
    test: freeContactEmail,
    why: "A hiring contact using a free email address is harder to link to an employer. Small businesses may use these addresses too.",
    whatToDo: "Verify the recruiter independently through the employer's official website before sharing documents.",
  },
  {
    name: "Pay that is far too high for the work",
    test: unrealisticPay,
    why: "Unusually high earnings paired with promises of very little work can be a way to draw you into a scam.",
    whatToDo: "Compare pay with similar roles and ask for the duties, pay structure and employment terms in writing.",
  },
  {
    name: "Urgency and pressure",
    test: pressureToAct,
    why: "Pressure to accept or respond immediately can leave you little time to check the employer and offer.",
    whatToDo: "Take time to verify the employer and request a written offer before sharing information or making a decision.",
  },
  {
    name: "Vague company or role",
    test: vagueRole,
    why: "Explicitly missing or withheld company details or job duties make it difficult to verify who is hiring and what you would do.",
    whatToDo: "Ask for the company name, exact role and duties in writing, then check the opening independently.",
  },
  {
    name: "Cheque or payment-forwarding tasks",
    test: chequeOrForwarding,
    why: "Cheques sent for equipment or requests to move money through your own account can leave you liable for reversed payments.",
    whatToDo: "Do not deposit the cheque or forward funds. Confirm the offer with the employer and speak with your bank before taking action.",
  },
  {
    name: "Poor grammar with a request for personal information",
    test: grammarWithPersonalRequest,
    why: "Clear grammar errors near a request for personal information are a reason to check the sender. Writing mistakes alone do not prove fraud.",
    whatToDo: "Verify the role through the employer's official contact channel before sending personal information.",
  },
];

function checkJobPost(text) {
  const source = typeof text === "string" ? text : "";
  return checks
    .filter((check) => check.test(source))
    .map(({ name, why, whatToDo }) => ({ name, why, whatToDo }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { checks, checkJobPost };
}

globalThis.safeJobCheck = { checks, checkJobPost };
