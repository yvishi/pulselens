// Every customer-facing string, keyed, in English (`en`) and plain Hindi (`hi`). strings.test.ts checks both have
// every key. The language follows navigator.language, with an EN/HI toggle on the consent screen.
// The customer never sees a score, family, check id or outcome: only these texts.
import type { CustomerMessage } from "../contracts";
import type { CaptureErrorDetail } from "../capture/session";
import type { CoachTip } from "../capture/coaching";
import type { TurnDirection } from "../capture/turnPrompt";

const en = {
  "consent.title": "Quick camera check",
  "frame.secure": "Secure video KYC check",
  "progress.label": "Steps",
  "progress.ready": "Get ready",
  "progress.camera": "Camera check",
  "progress.done": "Done",
  "consent.lead": "Here is what will happen:",
  "consent.item.colours": "Your screen shows a few soft colours.",
  "consent.item.turn": "You turn your head when asked.",
  "consent.item.time": "It takes about 20 seconds.",
  "consent.privacy": "We use your camera only for this check. Keep your face in view, in good light.",
  "consent.photosensitive":
    "If changing colours on a screen bother you, choose the second button: you will only be asked to turn your head.",
  "consent.start": "Start",
  "consent.noFlash": "I'd rather not see flashing colours",
  "lang.label": "Language",
  "lang.en": "English",
  "lang.hi": "हिंदी",
  "camera.asking": "Please allow camera access when your browser asks.",
  "preflight.checking": "Checking your camera…",
  "preflight.hint": "Hold the screen at eye level and keep your face in view.",
  "coaching.title": "Let's get a clearer picture",
  "coaching.hint": "We will continue in a few seconds.",
  "coach.light": "Face the light",
  "coach.backlight": "Too bright behind you",
  "coach.closer": "Move closer",
  "coach.shoulders": "Show your shoulders",
  "coach.still": "Hold still",
  "challenge.look": "Keep looking at the screen.",
  "turn.left": "Turn your head to your LEFT, then back to the centre",
  "turn.right": "Turn your head to your RIGHT, then back to the centre",
  "nod.prompt": "Nod your head: down, then back up",
  "digit.prompt": "Say this number out loud",
  "waiting.text": "Please wait…",
  "upload.weak": "Weak connection, still sending…",
  "result.continue": "Thank you, you can continue the call.",
  "result.please_retry": "Let's try that once more.",
  "result.please_retry.button": "Ask the agent for a new link",
  "result.please_retry.asked": "Please tell the agent on the call that you need a new link.",
  "result.please_wait": "Please wait for the agent.",
  "result.assisted_route": "The agent will help you complete KYC.",
  "agent.questions": "The agent will ask you a few questions.",
  "error.camera_denied": "We need your camera for video-KYC. You can also continue with the agent.",
  "error.camera_missing": "We could not find a camera on this device. You can also continue with the agent.",
  "error.camera_busy": "Another app is using your camera. Close it, or continue with the agent.",
  "error.camera_error": "We could not start your camera. You can also continue with the agent.",
  "error.insecure": "This page needs a secure (https) link to use the camera. Please ask the agent for a new link.",
  "error.expired": "This link has expired. Please ask the agent for a new link.",
  "error.failed": "Something went wrong. Please tell the agent; they will help you continue.",
  "error.no_token": "This link is incomplete. Please ask the agent for a new link.",
  "error.title": "We need to pause here",
  "error.next": "Stay on the call. The agent will tell you what to do next.",
} as const;

export type StringKey = keyof typeof en;
export type Lang = "en" | "hi";

const hi: Record<StringKey, string> = {
  "consent.title": "कैमरा से जल्दी जाँच",
  "frame.secure": "सुरक्षित वीडियो KYC जाँच",
  "progress.label": "चरण",
  "progress.ready": "तैयारी",
  "progress.camera": "कैमरा जाँच",
  "progress.done": "पूरा",
  "consent.lead": "आगे यह होगा:",
  "consent.item.colours": "आपकी स्क्रीन पर कुछ हल्के रंग दिखेंगे।",
  "consent.item.turn": "कहने पर आप अपना सिर घुमाएँगे।",
  "consent.item.time": "इसमें लगभग 20 सेकंड लगेंगे।",
  "consent.privacy": "हम आपका कैमरा सिर्फ़ इस जाँच के लिए इस्तेमाल करते हैं। अपना चेहरा कैमरे में और अच्छी रोशनी में रखें।",
  "consent.photosensitive":
    "अगर स्क्रीन पर बदलते रंगों से आपको परेशानी होती है, तो दूसरा बटन चुनें: आपसे सिर्फ़ सिर घुमाने को कहा जाएगा।",
  "consent.start": "शुरू करें",
  "consent.noFlash": "मुझे चमकते रंग नहीं देखने हैं",
  "lang.label": "भाषा",
  "lang.en": "English",
  "lang.hi": "हिंदी",
  "camera.asking": "जब आपका ब्राउज़र पूछे, तो कैमरा इस्तेमाल करने की अनुमति दें।",
  "preflight.checking": "आपका कैमरा जाँचा जा रहा है…",
  "preflight.hint": "स्क्रीन को आँखों की ऊँचाई पर रखें और अपना चेहरा कैमरे में रखें।",
  "coaching.title": "चलिए तस्वीर थोड़ी साफ़ करते हैं",
  "coaching.hint": "हम कुछ सेकंड में आगे बढ़ेंगे।",
  "coach.light": "रोशनी की तरफ़ मुँह करें",
  "coach.backlight": "आपके पीछे बहुत ज़्यादा रोशनी है",
  "coach.closer": "थोड़ा पास आएँ",
  "coach.shoulders": "अपने कंधे भी दिखाएँ",
  "coach.still": "हिलें नहीं, स्थिर रहें",
  "challenge.look": "स्क्रीन की ओर देखते रहें।",
  "turn.left": "अपना सिर अपनी बाईं (LEFT) ओर घुमाएँ, फिर वापस बीच में लाएँ",
  "turn.right": "अपना सिर अपनी दाईं (RIGHT) ओर घुमाएँ, फिर वापस बीच में लाएँ",
  "nod.prompt": "अपना सिर ऊपर-नीचे हिलाएँ: पहले नीचे, फिर वापस ऊपर",
  "digit.prompt": "यह अंक ज़ोर से बोलें",
  "waiting.text": "कृपया प्रतीक्षा करें…",
  "upload.weak": "कनेक्शन कमज़ोर है, फिर भी भेजा जा रहा है…",
  "result.continue": "धन्यवाद, आप कॉल जारी रख सकते हैं।",
  "result.please_retry": "चलिए, एक बार फिर से करते हैं।",
  "result.please_retry.button": "एजेंट से नया लिंक माँगें",
  "result.please_retry.asked": "कृपया कॉल पर एजेंट को बताएँ कि आपको नया लिंक चाहिए।",
  "result.please_wait": "कृपया एजेंट का इंतज़ार करें।",
  "result.assisted_route": "एजेंट KYC पूरा करने में आपकी मदद करेंगे।",
  "agent.questions": "एजेंट आपसे कुछ सवाल पूछेंगे।",
  "error.camera_denied": "वीडियो-KYC के लिए हमें आपका कैमरा चाहिए। आप एजेंट के साथ भी आगे बढ़ सकते हैं।",
  "error.camera_missing": "इस डिवाइस पर हमें कैमरा नहीं मिला। आप एजेंट के साथ भी आगे बढ़ सकते हैं।",
  "error.camera_busy": "आपका कैमरा कोई दूसरा ऐप इस्तेमाल कर रहा है। उसे बंद करें, या एजेंट के साथ आगे बढ़ें।",
  "error.camera_error": "हम आपका कैमरा शुरू नहीं कर पाए। आप एजेंट के साथ भी आगे बढ़ सकते हैं।",
  "error.insecure": "कैमरा इस्तेमाल करने के लिए इस पेज को सुरक्षित (https) लिंक चाहिए। कृपया एजेंट से नया लिंक माँगें।",
  "error.expired": "इस लिंक की समय-सीमा खत्म हो गई है। कृपया एजेंट से नया लिंक माँगें।",
  "error.failed": "कुछ गड़बड़ हो गई। कृपया एजेंट को बताएँ; वे आगे बढ़ने में आपकी मदद करेंगे।",
  "error.no_token": "यह लिंक अधूरा है। कृपया एजेंट से नया लिंक माँगें।",
  "error.title": "हमें यहाँ रुकना होगा",
  "error.next": "कॉल पर बने रहें। एजेंट आपको बताएँगे कि आगे क्या करना है।",
};

export const strings: Record<Lang, Record<StringKey, string>> = { en, hi };

/** Hindi when the browser language starts with "hi", else English. */
export function langFor(tag: string | undefined | null): Lang {
  return (tag ?? "").toLowerCase().startsWith("hi") ? "hi" : "en";
}

/** The starting language, from navigator.language. */
export const browserLang = (): Lang => langFor(typeof navigator === "undefined" ? undefined : navigator.language);

export function t(key: StringKey, lang: Lang = "en"): string {
  return strings[lang][key];
}

/** The only result text a customer sees, from CustomerStatus.message. */
export const resultKey = (m: CustomerMessage): StringKey => `result.${m}`;

export const errorKey = (d: CaptureErrorDetail | "no_token"): StringKey => `error.${d}`;

export const turnKey = (dir: TurnDirection): StringKey => `turn.${dir}`;

export const coachKey = (tip: CoachTip): StringKey => `coach.${tip}`;
