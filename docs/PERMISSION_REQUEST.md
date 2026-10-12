# Permission Request: Taadeel and the UAE Legislation Portal

Status: DRAFT, not sent. The sender completes the placeholders in square brackets and sends this letter personally. This document makes no claim of any prior contact, endorsement or communication with the recipient.

---

## English version

**Date:** [Date]

**To:** The General Secretariat of the UAE Cabinet (Cabinet General Secretariat), United Arab Emirates
**Attention:** The team responsible for the UAE Legislation portal (uaelegislation.gov.ae)

**From:** Huda Mueen, developer of Taadeel
**Contact email:** [Contact email]
**Project repository:** https://github.com/hudasol/Taadeel

**Subject:** Request for permission and guidance on automated read access, redisplay and comparison of legislation text from uaelegislation.gov.ae for a research and navigation tool

Dear Sir or Madam,

I am the developer of Taadeel (تعديل), an open source research and navigation tool that tracks amendments to UAE federal legislation. I write respectfully to request your permission and guidance before any real legislation text is collected, so that the project can operate within the terms you set.

### 1. What Taadeel does today

Taadeel is designed to answer two questions: what did a given law provide on a given date, and what has changed since. To do so it parses legislation into articles, aligns articles between versions, produces article level comparisons (diffs) and builds effective date timelines. The current state of the project is as follows.

- **Link first.** Every provision shown by the tool links to its official source on the portal, with a retrieval date. The tool directs users to the official publication.
- **No redistribution of portal text.** Taadeel does not currently copy, store or redistribute law text from the portal. No real UAE legislation is loaded.
- **Synthetic data, clearly labelled.** The parsing, alignment and comparison engine has been tested only on synthetic data, which is labelled as synthetic and kept separate from any real data views.
- **Not legal advice.** Taadeel is a research and navigation aid. It does not state the law and does not provide legal advice. The official Arabic text published by the competent authority prevails in every case.

### 2. Current access position

The portal does not, to my knowledge, publish an open licence or a documented API. In a single test, a request for the robots.txt file of the portal using curl returned HTTP status 403. I have made no further claim about the portal's technical measures, and I have not attempted to work around this response. Taadeel will not collect real text from the portal unless and until you permit it.

### 3. Requests

I respectfully request the following.

1. **Rate limited read access.** Permission for Taadeel to read pages of uaelegislation.gov.ae by automated means, at a low and rate limited volume, for the purpose of a research and navigation tool. I propose no more than one request every five seconds, a single connection, and off peak scheduling where practical, subject to any limits you prefer.
2. **Redisplay and comparison with attribution.** Permission to redisplay excerpts of legislation text, and to compute and display differences (diffs) of text between versions of the same legislation, in each case with clear attribution to the portal and a link to the official page.
3. **Licence and attribution wording.** Your preferred licence terms and the exact attribution wording you would like displayed (for example, source name, link, retrieval date and a disclaimer).
4. **Documented feed or bulk access.** If an official feed, API, bulk download or other structured channel exists or is planned, please share its documentation and terms, so that Taadeel can use it in place of page by page retrieval.
5. **Confirmation of what is not permitted.** A clear statement of any uses that are not permitted, including any restrictions on storage, republication, commercial use, translation, or use of the text with automated systems, so that the project can comply fully.

### 4. Commitments

If permission is granted, Taadeel will observe the following.

- **Identifying user agent.** Requests will carry a user agent that names the project, its repository and a contact email ([Contact email]), so that your team can reach me.
- **Crawl delay.** A fixed delay between requests (proposed above as at least five seconds), with backoff on any error or slow response.
- **robots.txt respected.** The robots.txt file and any crawl directives you publish will be read and followed.
- **No workarounds if blocked.** If access is blocked or refused, Taadeel will stop. It will not rotate addresses, disguise its identity, solve challenges or use any other means to avoid a block.
- **Scope and attribution.** Only the scope you approve will be retrieved. Attribution, retrieval dates and the research disclaimer will be shown with all content.
- **Prompt withdrawal.** If you ask me to stop, to change the rate or to remove any stored material, I will do so promptly.

### 5. Closing

I would be grateful for a written reply, including any conditions, by email to [Contact email]. I am happy to provide further details of the project, to demonstrate the tool on synthetic data, or to adjust the proposal to your requirements. Thank you for your time and consideration.

Yours faithfully,

Huda Mueen
Developer of Taadeel
https://github.com/hudasol/Taadeel
[Contact email]

---

## النسخة العربية

> **ملاحظة مهمة: هذه الترجمة العربية مسودة آلية (Machine drafted) وتحتاج إلى مراجعة من قارئ يجيد العربية القانونية بطلاقة قبل الإرسال. لا ينبغي إرسالها قبل المراجعة. النص الإنجليزي أعلاه هو المرجع.**

**التاريخ:** [Date]

**إلى:** الأمانة العامة لمجلس الوزراء (الأمانة العامة لمجلس الوزراء)، دولة الإمارات العربية المتحدة
**عناية:** الفريق المسؤول عن بوابة التشريعات في دولة الإمارات (uaelegislation.gov.ae)

**من:** هدى معين، مطورة منصة «تعديل» (Taadeel)
**البريد الإلكتروني للتواصل:** [Contact email]
**مستودع المشروع:** https://github.com/hudasol/Taadeel

**الموضوع:** طلب إذن وإرشاد بشأن الوصول الآلي للقراءة وإعادة العرض والمقارنة لنصوص التشريعات المنشورة على uaelegislation.gov.ae لأغراض أداة بحثية للتصفح والاسترشاد

سعادة المعنيين الكرام،

تحية طيبة وبعد،

أنا مطورة «تعديل» (Taadeel)، وهي أداة مفتوحة المصدر للبحث والتصفح تتتبع التعديلات التي تطرأ على التشريعات الاتحادية في دولة الإمارات العربية المتحدة. وأتقدم إليكم بهذا الطلب باحترام لاستئذانكم والاسترشاد بتوجيهاتكم قبل جمع أي نص تشريعي حقيقي، حتى يعمل المشروع ضمن الشروط التي تحددونها.

### 1. ما تقوم به المنصة حالياً

صُممت «تعديل» للإجابة عن سؤالين: ماذا كان يقرر تشريع معين في تاريخ معين، وما الذي تغير بعد ذلك. ولهذا الغرض تقوم بتحليل التشريعات إلى مواد، ومحاذاة المواد بين النسخ المختلفة، وإنتاج مقارنات على مستوى المادة (فروقات)، وبناء جداول زمنية لتواريخ النفاذ. وفيما يلي وضع المشروع الحالي.

- **الرابط أولاً.** كل حكم تعرضه الأداة يرتبط برابط إلى مصدره الرسمي على البوابة مع تاريخ الاسترجاع، وتوجه الأداة المستخدمين إلى النشر الرسمي.
- **لا إعادة توزيع لنصوص البوابة.** لا تنسخ «تعديل» حالياً نصوص القوانين من البوابة ولا تخزنها ولا تعيد توزيعها. ولم يتم تحميل أي تشريع إماراتي حقيقي.
- **بيانات اصطناعية موسومة بوضوح.** لم تُختبر منظومة التحليل والمحاذاة والمقارنة إلا على بيانات اصطناعية موسومة بأنها اصطناعية ومفصولة عن أي عروض لبيانات حقيقية.
- **ليست استشارة قانونية.** «تعديل» أداة مساعدة للبحث والتصفح، ولا تقرر القانون ولا تقدم استشارة قانونية. والنص العربي الرسمي الصادر عن الجهة المختصة هو المعتمد في جميع الأحوال.

### 2. وضع الوصول الحالي

على حد علمي، لا تنشر البوابة رخصة مفتوحة ولا واجهة برمجية موثقة. وفي اختبار واحد، أعاد طلب ملف robots.txt الخاص بالبوابة باستخدام أداة curl رمز الحالة 403. ولم أدّعِ أكثر من ذلك بشأن التدابير التقنية للبوابة، ولم أحاول تجاوز هذه الاستجابة. ولن تجمع «تعديل» أي نص حقيقي من البوابة ما لم تأذنوا بذلك وإلى حين صدور الإذن.

### 3. الطلبات

أتقدم باحترام بالطلبات الآتية.

1. **وصول للقراءة بمعدل محدود.** الإذن لـ«تعديل» بقراءة صفحات uaelegislation.gov.ae بوسائل آلية وبحجم منخفض ومعدل محدود، لأغراض أداة بحثية للتصفح والاسترشاد. وأقترح ألا يزيد المعدل عن طلب واحد كل خمس ثوانٍ، وباتصال واحد، وفي أوقات خارج الذروة متى أمكن، مع الالتزام بأي حدود تفضلونها.
2. **إعادة العرض والمقارنة مع الإسناد.** الإذن بإعادة عرض مقتطفات من نصوص التشريعات، وباحتساب وعرض الفروقات النصية بين نسخ التشريع نفسه، وفي كل حالة مع إسناد واضح إلى البوابة ورابط إلى الصفحة الرسمية.
3. **صيغة الترخيص والإسناد.** شروط الترخيص التي تفضلونها، والصيغة الدقيقة للإسناد التي ترغبون في عرضها (مثل اسم المصدر والرابط وتاريخ الاسترجاع وإخلاء المسؤولية).
4. **خدمة بيانات موثقة أو وصول مجمع.** إن وجدت أو كانت مخططة خدمة بيانات رسمية أو واجهة برمجية أو تنزيل مجمع أو أي قناة منظمة أخرى، فيرجى تزويدي بوثائقها وشروطها، لتستخدمها «تعديل» بدلاً من الاسترجاع صفحة بصفحة.
5. **تأكيد ما هو غير مسموح.** بيان واضح بأي استخدامات غير مسموح بها، بما في ذلك أي قيود على التخزين أو إعادة النشر أو الاستخدام التجاري أو الترجمة أو استخدام النصوص مع الأنظمة الآلية، حتى يلتزم المشروع التزاماً كاملاً.

### 4. التعهدات

في حال منح الإذن، ستلتزم «تعديل» بما يأتي.

- **معرّف مستخدم يحدد الهوية.** ستتضمن الطلبات معرّف مستخدم (user agent) يذكر اسم المشروع ومستودعه وبريداً إلكترونياً للتواصل ([Contact email]) ليتمكن فريقكم من الوصول إلي.
- **مهلة بين الطلبات.** مهلة ثابتة بين الطلبات (اقترحت أعلاه خمس ثوانٍ على الأقل) مع تخفيف المعدل عند أي خطأ أو بطء في الاستجابة.
- **احترام ملف robots.txt.** سيجري قراءة ملف robots.txt وأي توجيهات للزحف تنشرونها والالتزام بها.
- **لا التفاف عند الحظر.** إذا حُظر الوصول أو رُفض فستتوقف «تعديل». ولن تغيّر العناوين ولن تخفي هويتها ولن تحل اختبارات التحقق ولن تستخدم أي وسيلة أخرى لتجنب الحظر.
- **النطاق والإسناد.** لن يُسترجع إلا النطاق الذي توافقون عليه، وستُعرض مع كل المحتوى عبارات الإسناد وتواريخ الاسترجاع وإخلاء المسؤولية البحثي.
- **الاستجابة الفورية للإيقاف.** إذا طلبتم مني التوقف أو تغيير المعدل أو إزالة أي مواد مخزنة فسأفعل ذلك على الفور.

### 5. الخاتمة

أكون ممتنة لو وصلني رد خطي، يتضمن أي شروط، على البريد الإلكتروني [Contact email]. ويسعدني تقديم مزيد من التفاصيل عن المشروع، أو عرض الأداة على بيانات اصطناعية، أو تعديل المقترح بما يتوافق مع متطلباتكم. أشكركم على وقتكم واهتمامكم.

وتفضلوا بقبول فائق الاحترام،

هدى معين
مطورة «تعديل»
https://github.com/hudasol/Taadeel
[Contact email]
