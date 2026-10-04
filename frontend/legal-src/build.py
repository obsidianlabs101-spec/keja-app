import os
OUT=os.path.join(os.path.dirname(__file__),'..')
NAV=[("privacy.html","Privacy Policy"),("terms.html","Terms &amp; Conditions"),("listing-rules.html","Listing &amp; Community Rules"),("payments-refunds.html","Payments &amp; Refunds"),("safety-tips.html","Safety Tips"),("data-deletion.html","Delete My Data")]
def page(fname,title,body,intro=""):
    links=" ".join(f'<a href="{h}">{t}</a>' for h,t in NAV)
    html=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Keja</title><meta name="robots" content="index,follow">
<link rel="stylesheet" href="legal.css"><script src="legal-config.js"></script></head>
<body><header class="top"><a class="logo" href="/">keja</a><a class="back" href="/">← Back to Keja</a></header>
<main><h1>{title}</h1><p class="meta">Effective <span data-fill="effective">3 October 2026</span> · Operated by <span data-fill="company">Obsidian Labs</span></p>{intro}
{body}
<footer class="legal-foot"><p>{links}</p><p>Questions? Email <span data-fill="email">support email</span> or call/WhatsApp <span data-fill="phone">phone</span></p></footer></main></body></html>'''
    open(os.path.join(OUT,fname),'w',encoding='utf-8').write(html)

# ---------------------------------------------------------------- PRIVACY
privacy='''
<div class="note">This policy explains what personal information Keja collects, why, who sees it, and the choices you have. We follow the <b>Data Protection Act, 2019</b> of Kenya. If something here is unclear, email us — we'd rather explain than leave you guessing.</div>

<nav class="toc"><a href="#who">Who we are</a><a href="#collect">What we collect</a><a href="#use">How we use it</a><a href="#share">Who sees it</a><a href="#providers">Service providers</a><a href="#keep">How long we keep it</a><a href="#security">Security</a><a href="#rights">Your rights</a><a href="#kids">Children</a><a href="#local">Cookies &amp; storage</a><a href="#changes">Changes</a><a href="#contact">Contact</a></nav>

<h2 id="who">1. Who we are</h2>
<p>Keja is a property marketplace for Kenya (website and Android app) run by <b data-fill="company">Obsidian Labs</b> ("<b>Keja</b>", "<b>we</b>", "<b>us</b>"). We connect people looking for apartments, hostels, Airbnb-style stays and commercial spaces with landlords and agents. For the personal data described here, Keja is the <b>data controller</b>.</p>
<p>Contact: <span data-fill="email">support email</span> · <span data-fill="address">Nairobi, Kenya</span></p>
<p data-optional style="display:block">Office of the Data Protection Commissioner (ODPC) registration no.: <span data-fill="odpcReg"></span></p>

<h2 id="collect">2. What we collect</h2>
<h3>Information you give us</h3>
<ul>
<li><b>Account details:</b> full name, username, email address, phone number, and a password (we store only a scrambled "hash", never the password itself). If you use <b>Sign in with Google</b>, we receive your name, email address and profile photo from Google.</li>
<li><b>Profile photo</b> (optional).</li>
<li><b>Landlord verification:</b> if you apply to be a verified landlord, we collect an <b>image of your national ID or passport</b> and related details so our team can confirm who you are. This is sensitive; only authorised Keja admins can open it.</li>
<li><b>Listings you post (landlords):</b> property type, price, location, description, amenities, photos, availability, and the contact number you provide.</li>
<li><b>Things you do in the app:</b> properties you mark as interested or swipe on, property alerts you set (area, price range), comments you leave about a landlord, and referrals you make or use.</li>
<li><b>Payment details:</b> to unlock a landlord's contact we ask you to pay KES 50 by M-Pesa and paste the M-Pesa confirmation message. We keep that message (which includes the transaction code, amount, date and the payer's name/number as it appears in the message). We do <b>not</b> see or store your M-Pesa PIN, and we never ask for it.</li>
<li><b>Messages to us:</b> emails or support requests you send.</li>
</ul>
<h3>Information collected automatically</h3>
<ul>
<li><b>Technical data:</b> IP address, app/browser version and device type, used for security, abuse prevention and rate limiting.</li>
<li><b>Notifications:</b> the Android app checks for new alerts in the background (about every 15 minutes) so it can show you notifications. This is a periodic check, not location tracking.</li>
<li><b>Local storage:</b> see <a href="#local">Cookies &amp; storage</a>.</li>
</ul>
<h3>What we do <u>not</u> collect</h3>
<p>We do not track your precise GPS location, read your contacts, or access your SMS inbox. Areas you search for are only what you type.</p>

<h2 id="use">3. How we use your information (and why we're allowed to)</h2>
<table><tr><th>Purpose</th><th>Basis (Data Protection Act)</th></tr>
<tr><td>Create and run your account; show listings; let landlords and renters connect</td><td>Contract / steps you ask for</td></tr>
<tr><td>Process contact-unlock payments, review payment claims, deliver a landlord's number to a paying renter</td><td>Contract; legitimate interests</td></tr>
<tr><td>Verify landlords and keep the platform trustworthy (moderating listings, fighting fraud and fake accounts)</td><td>Your consent (for ID checks); legitimate interests</td></tr>
<tr><td>Send verification links, alerts and service messages (e.g. "your landlord's number is ready")</td><td>Contract; legitimate interests</td></tr>
<tr><td>Keep the service secure, prevent abuse, fix bugs</td><td>Legitimate interests; legal obligation</td></tr>
<tr><td>Show you advertising banners placed by Keja admins (these are not personalised using your data)</td><td>Legitimate interests</td></tr>
<tr><td>Comply with the law and respond to lawful requests</td><td>Legal obligation</td></tr></table>
<p>We do <b>not</b> sell your personal data, and we do not use it for automated decisions that significantly affect you.</p>

<h2 id="share">4. Who can see your information</h2>
<ul>
<li><b>Other users — what is public:</b> a landlord's name, username, profile photo, verified badge, listings and the comments renters leave appear to other users. Your comments show your name and photo.</li>
<li><b>Landlord phone numbers:</b> a landlord's phone number is <b>hidden</b> until a renter unlocks it by paying KES 50 or using a free referral unlock. By posting a listing, landlords agree that their number will be shown to renters who unlock it.</li>
<li><b>Renters:</b> your name and contact details are <b>not</b> shown to landlords unless you contact them yourself.</li>
<li><b>Keja admins:</b> a small number of authorised staff can view account details, listings, payment claims and ID verification images to run and moderate the service.</li>
<li><b>Authorities:</b> we may disclose information if required by law, a court order, or to protect people from fraud or harm.</li>
</ul>

<h2 id="providers">5. Service providers we use</h2>
<p>We use trusted companies to run Keja. They only process data on our instructions:</p>
<table><tr><th>Provider</th><th>What for</th></tr>
<tr><td>Render</td><td>Hosting the website and server</td></tr>
<tr><td>Supabase</td><td>Database and file storage (listings, photos, account records)</td></tr>
<tr><td>Google (Sign in with Google; Gmail)</td><td>Optional sign-in; sending verification emails</td></tr>
<tr><td>Brevo (only if enabled)</td><td>Sending verification emails</td></tr>
<tr><td>GitHub</td><td>Distributing the Android app file (no personal data about you is sent to GitHub by the app)</td></tr>
<tr><td>Safaricom M-Pesa</td><td>Payment of the unlock fee (you pay in the M-Pesa app; we only receive the confirmation message you paste)</td></tr></table>
<p><b>Transfers outside Kenya.</b> Some of these providers store data on servers outside Kenya. Where that happens we rely on appropriate safeguards as required by the Data Protection Act, 2019.</p>

<h2 id="keep">6. How long we keep it</h2>
<ul>
<li><b>Account and profile data:</b> while your account is active. If you ask us to delete your account, we delete or anonymise it within <b>30 days</b>, except records we must keep by law.</li>
<li><b>ID verification images:</b> kept while your landlord verification is active, and removed on request or within <b>30 days</b> of your account being deleted.</li>
<li><b>Payment records (M-Pesa messages, transaction codes):</b> kept for up to <b>7 years</b> for accounting, dispute and anti-fraud purposes.</li>
<li><b>Listings and comments:</b> removed when you delete them or your account (comments may be anonymised).</li>
<li><b>Security logs / IP addresses:</b> kept for a short period (typically up to 90 days).</li>
</ul>

<h2 id="security">7. How we protect it</h2>
<p>Passwords are hashed; traffic is encrypted with HTTPS; access to admin tools and ID images is restricted to authorised staff; login and sensitive actions are rate-limited; and verification links are signed and expire. No system is perfectly secure — please choose a strong, unique password and never share it. If we discover a breach affecting you, we will notify you and the ODPC as the law requires.</p>

<h2 id="rights">8. Your rights</h2>
<p>Under the Data Protection Act, 2019 you can:</p>
<ul><li><b>Be informed</b> about how we use your data (this policy).</li><li><b>Access</b> a copy of the personal data we hold about you.</li><li><b>Correct</b> data that is wrong or out of date.</li><li><b>Delete</b> your data (see <a href="data-deletion.html">Delete My Data</a>).</li><li><b>Object</b> to, or ask us to restrict, certain uses.</li><li><b>Move</b> your data to another service (data portability).</li><li><b>Withdraw consent</b> at any time (e.g. for ID verification) — this won't affect what we did before.</li></ul>
<p>To use a right, email <span data-fill="email">support email</span> from the address on your account. We'll reply within <b>30 days</b>. If you're unhappy with our answer, you can complain to the <b>Office of the Data Protection Commissioner</b> (Kenya) at <a href="https://www.odpc.go.ke" rel="noopener">www.odpc.go.ke</a>.</p>

<h2 id="kids">9. Children</h2>
<p>Keja is for people aged <b>18 and over</b>. We don't knowingly collect data from children. If you believe a child has created an account, tell us and we'll delete it.</p>

<h2 id="local">10. Cookies &amp; local storage</h2>
<p>We don't use advertising or tracking cookies. The website and app store a few things on your device so they work properly:</p>
<ul><li>your <b>login token</b> (so you stay logged in until you log out),</li><li>your <b>appearance choice</b> (theme / light or dark),</li><li>small pieces of app state (e.g. a "seen this prompt" flag) and a cache so pages load faster.</li></ul>
<p>Logging out removes the login token. You can clear the rest in your browser or phone settings.</p>

<h2 id="changes">11. Changes to this policy</h2>
<p>If we make important changes we'll tell you in the app or by email and update the date at the top. Using Keja after a change means you accept the updated policy.</p>

<h2 id="contact">12. Contact us</h2>
<p><b data-fill="company">Obsidian Labs</b><br><span data-fill="address">Nairobi, Kenya</span><br><span data-fill="email">support email</span><br><span data-fill="phone">phone</span></p>
'''
page("privacy.html","Privacy Policy",privacy)

# ---------------------------------------------------------------- TERMS
terms='''
<div class="note"><b>The short version:</b> Keja helps renters and landlords find each other. We are a marketplace — we are <u>not</u> the landlord, agent or party to any tenancy. Check properties in person before paying any deposit or rent, and never pay a landlord money you can't verify. Please read the full terms below; by creating an account or using Keja you agree to them.</div>

<nav class="toc"><a href="#accept">Acceptance</a><a href="#eligible">Eligibility</a><a href="#accounts">Accounts</a><a href="#role">Our role</a><a href="#renters">Renters</a><a href="#landlords">Landlords</a><a href="#fees">Fees</a><a href="#content">Your content</a><a href="#conduct">Acceptable use</a><a href="#ads">Ads &amp; links</a><a href="#disclaimer">Disclaimers</a><a href="#liability">Liability</a><a href="#end">Ending</a><a href="#law">Law</a></nav>

<h2 id="accept">1. Agreement</h2>
<p>These Terms &amp; Conditions ("<b>Terms</b>") are a binding agreement between you and <b data-fill="company">Obsidian Labs</b> ("<b>Keja</b>", "<b>we</b>") covering the Keja website, Android app and related services (the "<b>Service</b>"). They include our <a href="privacy.html">Privacy Policy</a>, <a href="listing-rules.html">Listing &amp; Community Rules</a> and <a href="payments-refunds.html">Payments &amp; Refunds</a> policy. If you don't agree, please don't use Keja.</p>

<h2 id="eligible">2. Who can use Keja</h2>
<p>You must be <b>18 or older</b> and able to enter a legally binding contract in Kenya. By using Keja you confirm the information you give us is true.</p>

<h2 id="accounts">3. Your account</h2>
<ul><li>Sign up with a real email address you own. We may send you a link to verify it and you may not be able to log in until you do.</li>
<li>Keep your password secret. You are responsible for activity on your account. Tell us straight away if you think someone else is using it.</li>
<li>One person, one account. Don't create fake or duplicate accounts, including to claim free referral unlocks.</li>
<li>We may suspend or close accounts that break these Terms or put others at risk.</li></ul>

<h2 id="role">4. What Keja is — and isn't</h2>
<ul><li>Keja is an <b>online marketplace and introduction service</b>. Landlords and agents list properties; renters and buyers discover them and can unlock a landlord's contact.</li>
<li>Keja is <b>not</b> a landlord, estate agent, broker or property manager, and is <b>not a party</b> to any tenancy, sale, booking or payment between users. Any agreement is strictly between you and the other person.</li>
<li>We don't own, inspect or guarantee any property, and we don't collect or hold rent, deposits, booking fees or sale payments.</li>
<li>Listings, prices and availability are provided by landlords. We try to keep information accurate, but we cannot promise that any listing is current, correct or available. The "Verified" badge means an admin reviewed that landlord's ID — it is <b>not</b> a guarantee about the property, the landlord's conduct, or a recommendation.</li></ul>

<h2 id="renters">5. If you are a renter or buyer</h2>
<ul><li>Do your own checks: <b>view the property in person</b>, confirm the person you are dealing with owns or is authorised to let it, and read any agreement before you sign.</li>
<li><b>Never pay rent, a deposit or a "viewing fee" to someone you haven't met or can't verify.</b> See our <a href="safety-tips.html">Safety Tips</a>.</li>
<li>Don't use landlords' contact details for anything other than enquiring about their property. No spam, harassment or reselling of contact details.</li>
<li>Comments you leave about landlords must be honest, based on your own experience, and follow our <a href="listing-rules.html">Community Rules</a>.</li></ul>

<h2 id="landlords">6. If you are a landlord or agent</h2>
<ul><li>You confirm you own the property or have the owner's written authority to advertise it.</li>
<li>Listings must be <b>accurate and current</b>: real photos of the actual property, correct price, location and type, and any agent fee clearly stated. Mark a property as booked or remove it when it is no longer available.</li>
<li>You agree that your phone number will be shown to renters who unlock it, and that renters may leave public comments about you.</li>
<li>Don't charge renters for viewings or ask for payment before they have seen the property, and don't pressure anyone to pay a deposit. Follow all laws that apply to letting property in Kenya, including tenancy, consumer protection and tax laws.</li>
<li>We may review, reject, edit or remove listings and verification requests at our discretion, including any that look misleading, duplicate or unsafe.</li>
<li>You are responsible for your dealings with renters. Keja is not liable for disputes between you and a renter.</li></ul>

<h2 id="fees">7. Fees and payments</h2>
<ul><li>Listing a property on Keja is currently <b>free</b>.</li>
<li>Renters pay <b>KES 50</b> by M-Pesa to unlock a landlord's contact for a listing, or can use a one-time free referral unlock when it is available. Fees are shown before you pay and may change (changes apply to future payments only).</li>
<li>Payments are confirmed by our team from the M-Pesa message you submit. The detailed rules, including refunds, are in <a href="payments-refunds.html">Payments &amp; Refunds</a>.</li>
<li>We are not responsible for fees charged by Safaricom or your mobile provider.</li></ul>

<h2 id="content">8. Your content</h2>
<p>You keep ownership of the photos, text and comments you post ("<b>Your Content</b>"). By posting it, you give Keja a free, non-exclusive licence to host, display, reproduce and distribute it inside the Service (including to promote listings within Keja) for as long as it stays on Keja. You confirm that you have the rights to what you post and that it doesn't infringe anyone's rights (for example, don't use photos you copied from another site). We can remove content that breaks these Terms.</p>

<h2 id="conduct">9. Acceptable use</h2>
<p>You agree not to: post false, misleading or fraudulent listings; impersonate anyone; harass, threaten or discriminate against others; post unlawful, hateful, sexual or defamatory content; scrape, copy or resell Keja's data; attempt to access other people's accounts or our systems; upload malware; exploit bugs or referral rewards; or use Keja for anything illegal under Kenyan law (including the Computer Misuse and Cybercrimes Act, 2018). More detail is in the <a href="listing-rules.html">Listing &amp; Community Rules</a>.</p>

<h2 id="ads">10. Ads and third-party links</h2>
<p>Keja may show banners placed by advertisers or Keja. We don't endorse advertisers or third-party sites and aren't responsible for their content, products or conduct. Dealings with them are at your own risk.</p>

<h2 id="disclaimer">11. Disclaimers</h2>
<p>The Service is provided <b>"as is" and "as available"</b>. To the fullest extent the law allows, we don't promise that Keja will be uninterrupted, error-free or secure, or that any listing, landlord or renter is genuine, suitable or reliable. Nothing in these Terms limits your rights under Kenya's Consumer Protection Act, 2012, where those rights apply.</p>

<h2 id="liability">12. Limit of our responsibility</h2>
<p>To the extent allowed by law, Keja is not liable for any loss arising from your dealings with other users, from relying on a listing, from a property being unavailable or unsuitable, or from indirect or consequential losses (such as lost income or opportunity). Our total liability to you for any claim relating to the Service is limited to the amount you paid Keja in the <b>12 months</b> before the claim (or KES 1,000 if you paid nothing). Nothing here excludes liability that cannot be excluded by law, such as for fraud or for death or personal injury caused by negligence.</p>
<p>You agree to compensate Keja for losses caused by your breach of these Terms or your unlawful use of the Service (for example, a false listing that leads to a claim against us).</p>

<h2 id="end">13. Ending your use</h2>
<p>You can stop using Keja at any time and ask us to <a href="data-deletion.html">delete your data</a>. We may suspend or terminate your access if you break these Terms, if we must by law, or if we stop offering the Service. Fees already paid for a completed unlock are not refundable except as set out in the <a href="payments-refunds.html">Payments &amp; Refunds</a> policy.</p>

<h2 id="law">14. Changes, law and disputes</h2>
<ul><li><b>Changes:</b> we may update these Terms. We'll tell you about important changes in the app or by email. Continuing to use Keja after a change means you accept it.</li>
<li><b>Governing law:</b> these Terms are governed by the laws of <b>Kenya</b>.</li>
<li><b>Disputes:</b> please contact us first at <span data-fill="email">support email</span> so we can try to fix it. If we can't, the courts of Kenya (Nairobi) have jurisdiction.</li>
<li>If any part of these Terms is found unenforceable, the rest stays in force.</li></ul>
<p><b>Contact:</b> <b data-fill="company">Obsidian Labs</b>, <span data-fill="address">Nairobi, Kenya</span>, <span data-fill="email">support email</span></p>
'''
page("terms.html","Terms &amp; Conditions",terms)

# ---------------------------------------------------------------- LISTING RULES
rules='''
<div class="note">Keja only works if listings are real and people are respectful. These rules apply to everyone: landlords, agents and renters.</div>
<h2>Listings: what we require</h2>
<ul><li><b>Real property, real photos.</b> Photos must show the actual property you are advertising. No stock images, no photos copied from other sites or listings.</li>
<li><b>Honest details.</b> Correct price, location, property type (apartment, hostel, Airbnb, shop…), number of rooms and amenities. State any agent fee up front.</li>
<li><b>One listing per property.</b> No duplicates, and no listings for properties you don't own or aren't authorised to let.</li>
<li><b>Keep it current.</b> Mark a property <i>booked</i> or remove it when it's taken. Listings that are stale or repeatedly unavailable may be removed.</li>
<li><b>Correct category.</b> Put hostels in Hostels, short stays in Airbnb, and so on, so renters find what they expect.</li></ul>
<h2>Never allowed</h2>
<ul><li>Fake, "bait-and-switch" or scam listings; asking renters to pay for a viewing, "booking" or deposit before they've seen the property.</li>
<li>Discrimination in a listing on the basis of tribe, race, religion, gender, disability or similar grounds.</li>
<li>Illegal uses (for example, properties used for unlawful activity) or content that is violent, sexual, hateful or harassing.</li>
<li>Personal data of other people (their ID, phone numbers or photos) without their permission.</li>
<li>Phone numbers, emails or links in photos or descriptions to dodge the contact-unlock system.</li>
<li>Creating several accounts, or using fake accounts to claim free referral unlocks or to post fake comments.</li></ul>
<h2>Comments about landlords</h2>
<ul><li>You can leave <b>one comment per landlord</b>. Say what really happened to you — be fair and factual.</li>
<li>No insults, threats, hate, private information, or accusations you can't back up. Don't comment on yourself or on behalf of friends or family you're paid to support.</li>
<li>You can edit or delete your own comment at any time.</li></ul>
<h2>Reporting a problem</h2>
<p>If you see a fake listing, a scam, an abusive comment or a stolen photo, email <span data-fill="email">support email</span> with the listing or landlord name and what's wrong. We review reports promptly and may remove content, suspend accounts, and where appropriate report to the police.</p>
<h2>What happens if rules are broken</h2>
<p>We may reject or remove listings and comments, remove a verified badge, suspend or close accounts, and, where the law requires, share information with the authorities. Serious or repeated breaches can mean a permanent ban.</p>
'''
page("listing-rules.html","Listing &amp; Community Rules",rules)

# ---------------------------------------------------------------- PAYMENTS & REFUNDS
pay='''
<div class="note">Keja never asks for your M-Pesa PIN, never collects rent or deposits, and only charges <b>KES 50</b> to unlock a landlord's contact. If anyone asks you for more money "on behalf of Keja", it is a scam — tell us.</div>
<h2>1. What you pay for</h2>
<p>Landlord phone numbers are hidden. To see a landlord's number for a listing, a renter either pays a <b>KES 50 unlock fee</b> or uses a one-time <b>free referral unlock</b>. The fee covers the cost of running the platform and checking landlords. It is <b>not</b> rent, a deposit, a booking fee or a commission for the property.</p>
<h2>2. How to pay</h2>
<ol><li>Open M-Pesa, choose <b>Lipa na M-Pesa → Buy Goods and Services</b>.</li>
<li>Enter the Till number shown in the app (currently <b>4396353</b>, business name <b>Obsidian Labs</b>) and the amount (KES 50). Check the name reads <b>Obsidian Labs</b> before entering your PIN.</li>
<li>Copy the M-Pesa confirmation message and paste it into Keja.</li>
<li>Our team checks the payment. When it is confirmed, the landlord's number is sent to your <b>Alerts</b> (the bell). We aim to review claims within <b>24 hours</b>, usually much faster.</li></ol>
<p>Payments are checked manually, so the number does not appear instantly.</p>
<h2>3. Free referral unlock</h2>
<p>Share your referral link. When a friend creates a <b>real, verified account</b> with it, you get one free unlock. Each person can receive this bonus once. Fake or duplicate accounts don't count and can lead to the bonus being withdrawn and the accounts closed.</p>
<h2>4. Refunds</h2>
<p>Because the number is a digital service delivered as soon as your payment is confirmed, unlock fees are <b>generally non-refundable</b>. We <b>will</b> refund (or give you a free unlock instead, if you prefer) in these cases:</p>
<ul><li>You paid but did <b>not receive the number</b> within 48 hours of sending your payment message.</li>
<li>You paid <b>twice</b> for the same listing by mistake.</li>
<li>The listing was <b>removed or marked booked before</b> your payment was confirmed and you didn't get the number.</li>
<li>The number we delivered was clearly <b>wrong</b> (for example, not in service).</li></ul>
<p>We can't refund a fee because you changed your mind, the property wasn't what you expected, the landlord didn't answer, or you and the landlord couldn't agree — Keja is not part of that arrangement (see our <a href="terms.html">Terms</a>).</p>
<h2>5. How to ask for a refund</h2>
<p>Email <span data-fill="email">support email</span> within <b>14 days</b> of payment with: the phone number you paid from, the M-Pesa confirmation message, and the listing. We reply within 3 working days. Approved refunds are sent back by M-Pesa to the number you paid from.</p>
<h2>6. Rent and deposits are between you and the landlord</h2>
<p>Keja is not involved in rent, deposits, viewing fees or sale payments. We cannot recover money you pay to a landlord or agent, so view the property and verify the person first. Read our <a href="safety-tips.html">Safety Tips</a>.</p>
<h2>7. Changes</h2>
<p>Fees and this policy may change. Any change applies only to payments made after it is published.</p>
'''
page("payments-refunds.html","Payments &amp; Refunds",pay)

# ---------------------------------------------------------------- SAFETY TIPS
safety='''
<div class="note">Rental scams are common. A few simple habits will protect you and your money.</div>
<h2>Before you pay anyone</h2>
<ul><li><b>See it first.</b> Visit the property in person (take a friend or tell someone where you're going). Never pay a deposit or rent for a place you haven't seen.</li>
<li><b>Meet the right person.</b> Ask who owns or manages the property. A genuine landlord or agent will show the keys, the unit and proof of authority. Check the landlord's profile on Keja — a <b>✓ Verified</b> badge means an admin checked their ID, but still do your own checks.</li>
<li><b>Beware "viewing fees" and urgency.</b> Anyone asking for money just to show a house, or saying "many people are paying today", is a red flag.</li>
<li><b>Too good to be true?</b> Prices far below the area's normal rent, or photos that look like a hotel or a foreign home, are warning signs.</li></ul>
<h2>When you pay a deposit or rent</h2>
<ul><li>Pay to a <b>name that matches</b> the owner or the registered agency, and get a <b>signed receipt and tenancy agreement</b> before or at the time you pay.</li>
<li>Read the agreement: rent, deposit, notice period, who pays water/electricity/service charge.</li>
<li>Pay by traceable methods (M-Pesa to a verified number or bank) — avoid large cash payments to individuals you can't trace.</li></ul>
<h2>About Keja payments</h2>
<ul><li>Keja only charges <b>KES 50</b> to unlock a contact, paid to Till <b>4396353 (Obsidian Labs)</b>.</li>
<li>We will <b>never</b> ask for your M-Pesa PIN, a deposit, or rent. Never share your PIN or an M-Pesa one-time code with anyone.</li></ul>
<h2>Hostels and short stays</h2>
<ul><li>For hostels, check the security (gate, guard, locks), the shared facilities, and the house rules before paying a semester deposit. Ask the student you're replacing, if any.</li>
<li>For Airbnb-style stays, confirm check-in details and the exact address before travelling; avoid paying fully upfront to someone you haven't verified.</li></ul>
<h2>Report it</h2>
<p>If something feels wrong, stop and tell us at <span data-fill="email">support email</span>. If you've been defrauded, report to your nearest police station (DCI) and to Safaricom if M-Pesa was involved.</p>
'''
page("safety-tips.html","Safety Tips",safety)

# ---------------------------------------------------------------- DATA DELETION
dele='''
<div class="note">You can ask us to delete your Keja account and the personal data linked to it at any time. This page tells you how and what happens.</div>
<h2>How to request deletion</h2>
<ol><li>Email <span data-fill="email">support email</span> from the <b>email address on your account</b> (so we know it's really you).</li>
<li>Use the subject <b>"Delete my Keja account"</b>. Include your username. You don't need to give a reason.</li>
<li>We'll reply to confirm, and complete the deletion within <b>30 days</b> (usually sooner).</li></ol>
<p>If you only want some data removed (for example your ID image, your profile photo, or a comment), say so in the email and we'll do just that.</p>
<h2>What we delete</h2>
<ul><li>Your profile: name, username, email, phone, profile photo and password.</li>
<li>Your saved/interested properties, property alerts, notifications and referral records.</li>
<li>Your ID verification image and details (if you were a verified landlord).</li>
<li>Your listings and their photos (landlords), and your comments (deleted or anonymised).</li></ul>
<h2>What we may keep, and why</h2>
<ul><li><b>Payment records</b> (M-Pesa confirmation messages and transaction codes) for up to <b>7 years</b> — needed for accounting, tax and dispute/fraud checks. They are kept securely and aren't used for anything else.</li>
<li><b>Records we must keep by law</b>, or need to handle an open dispute or investigation.</li>
<li><b>Backups</b> may hold data for a short time and are overwritten on a normal cycle.</li></ul>
<h2>Before you delete</h2>
<p>Deletion is permanent. You'll lose your saved properties and any unlocked contacts, and landlords will lose their listings and comments. If you've paid for an unlock, the number stays with you only as long as your account exists.</p>
<h2>Other requests</h2>
<p>To get a copy of your data, correct it, or object to how we use it, email the same address. See the <a href="privacy.html#rights">Privacy Policy</a> for your rights, and how to complain to Kenya's Office of the Data Protection Commissioner (<a href="https://www.odpc.go.ke" rel="noopener">odpc.go.ke</a>).</p>
'''
page("data-deletion.html","Delete My Data",dele)

# ---------------------------------------------------------------- INDEX
idx='''
<p>Everything you should know about using Keja, in plain language.</p>
<ul style="list-style:none;padding:0">
<li style="margin:12px 0"><a href="privacy.html"><b>Privacy Policy</b></a><br><span class="meta">What we collect, why, and your rights.</span></li>
<li style="margin:12px 0"><a href="terms.html"><b>Terms &amp; Conditions</b></a><br><span class="meta">The rules for using Keja as a renter or landlord.</span></li>
<li style="margin:12px 0"><a href="listing-rules.html"><b>Listing &amp; Community Rules</b></a><br><span class="meta">What makes a good listing and respectful comment.</span></li>
<li style="margin:12px 0"><a href="payments-refunds.html"><b>Payments &amp; Refunds</b></a><br><span class="meta">The KES 50 unlock fee and when we refund it.</span></li>
<li style="margin:12px 0"><a href="safety-tips.html"><b>Safety Tips</b></a><br><span class="meta">How to avoid rental scams.</span></li>
<li style="margin:12px 0"><a href="data-deletion.html"><b>Delete My Data</b></a><br><span class="meta">How to close your account and remove your data.</span></li></ul>
'''
page("legal.html","Legal &amp; Safety",idx)
print("built")
