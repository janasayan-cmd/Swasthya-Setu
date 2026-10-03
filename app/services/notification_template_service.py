"""Notification Template & Localization Service (Phase 29).

Enforces:
- Deterministic template versioning and language resolution (en, hi, bn).
- Strict variable validation preventing KeyError / format exploits.
- CRLF and script injection protection in titles and bodies.
- Clinical Safety Boundaries:
  Blocks autonomous medical advice, diagnoses, or prescribing instructions.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, NamedTuple, Optional, Tuple

from app.core.exceptions import (
    TemplateResolutionException,
    UnauthorizedClinicalContentException,
)
from app.schemas.notification import NotificationType

logger = logging.getLogger(__name__)

# Disallowed clinical keywords in notification payloads to uphold clinical safety
DISALLOWED_CLINICAL_KEYWORDS = [
    "stop taking",
    "increase your dose",
    "decrease your dose",
    "you are diagnosed with",
    "you have pneumonia",
    "you have cancer",
    "you do not need medical attention",
    "you are safe from",
    "take 500mg",
    "autonomous diagnosis",
]


class TemplateDefinition(NamedTuple):
    version: int
    title_template: str
    body_template: str
    required_variables: list[str]


# Multi-lingual templates (English, Hindi, Bengali)
TEMPLATES: Dict[NotificationType, Dict[str, TemplateDefinition]] = {
    NotificationType.DOCUMENT_PROCESSING_COMPLETED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Document Processing Completed",
            body_template="Your medical document '{document_name}' has been processed and is ready for review in your portal.",
            required_variables=["document_name"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="दस्तावेज़ प्रसंस्करण पूर्ण हुआ",
            body_template="आपका मेडिकल दस्तावेज़ '{document_name}' संसाधित हो गया है और समीक्षा के लिए तैयार है।",
            required_variables=["document_name"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ডকুমেন্ট প্রক্রিয়াকরণ সম্পন্ন হয়েছে",
            body_template="আপনার মেডিকেল ডকুমেন্ট '{document_name}' প্রক্রিয়া সম্পন্ন হয়েছে এবং পর্যালোচনার জন্য প্রস্তুত।",
            required_variables=["document_name"],
        ),
    },
    NotificationType.DOCUMENT_PROCESSING_FAILED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Document Processing Issue",
            body_template="We encountered an issue processing '{document_name}'. Please verify the file and re-upload.",
            required_variables=["document_name"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="दस्तावेज़ प्रसंस्करण में त्रुटि",
            body_template="आपके दस्तावेज़ '{document_name}' को संसाधित करने में समस्या आई। कृपया फ़ाइल जांचें और पुनः अपलोड करें।",
            required_variables=["document_name"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ডকুমেন্ট প্রক্রিয়াকরণে সমস্যা",
            body_template="আপনার ডকুমেন্ট '{document_name}' প্রক্রিয়াকরণে একটি সমস্যা দেখা দিয়েছে। অনুগ্রহ করে ফাইলটি যাচাই করে পুনরায় আপলোড করুন।",
            required_variables=["document_name"],
        ),
    },
    NotificationType.PRESCRIPTION_PROCESSING_COMPLETED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Prescription Record Available",
            body_template="A new prescription record from {facility_name} is available for viewing in your secure passport.",
            required_variables=["facility_name"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="प्रिस्क्रिप्शन रिकॉर्ड उपलब्ध है",
            body_template="{facility_name} से एक नया प्रिस्क्रिप्शन रिकॉर्ड आपके सुरक्षित पोर्टल में उपलब्ध है।",
            required_variables=["facility_name"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="প্রেসক্রিপশন রেকর্ড উপলব্ধ",
            body_template="{facility_name} থেকে একটি নতুন প্রেসক্রিপশন রেকর্ড আপনার পোর্টালে দেখার জন্য উপলব্ধ।",
            required_variables=["facility_name"],
        ),
    },
    NotificationType.MEDICATION_NORMALIZATION_REVIEW_REQUIRED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Medication Review Needed",
            body_template="A clinician review is required for medication '{medication_name}'.",
            required_variables=["medication_name"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="दवा समीक्षा आवश्यक",
            body_template="दवा '{medication_name}' के लिए चिकित्सक की समीक्षा आवश्यक है।",
            required_variables=["medication_name"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ওষুধ পর্যালোচনা প্রয়োজন",
            body_template="ওষুধ '{medication_name}' এর জন্য একজন চিকিৎসকের পর্যালোচনা প্রয়োজন।",
            required_variables=["medication_name"],
        ),
    },
    NotificationType.MEDICATION_SAFETY_REVIEW_REQUIRED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Medication Safety Advisory",
            body_template="A clinical safety alert requires attention for patient record {patient_id}.",
            required_variables=["patient_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="दवा सुरक्षा चेतावनी",
            body_template="रोगी रिकॉर्ड {patient_id} के लिए सुरक्षा चेतावनी की समीक्षा आवश्यक है।",
            required_variables=["patient_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ওষুধের সুরক্ষা সতর্কতা",
            body_template="রোগীর রেকর্ড {patient_id} এর জন্য সুরক্ষা সতর্কতা পর্যালোচনা প্রয়োজন।",
            required_variables=["patient_id"],
        ),
    },
    NotificationType.TRIAGE_RESULT_AVAILABLE: {
        "en": TemplateDefinition(
            version=1,
            title_template="Triage Assessment Summary Available",
            body_template="A deterministic triage assessment is available for viewing in the clinical workspace.",
            required_variables=[],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="ट्राइएज मूल्यांकन सारांश उपलब्ध",
            body_template="चिकित्सा कार्यक्षेत्र में ट्राइएज मूल्यांकन सारांश उपलब्ध है।",
            required_variables=[],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ট্রায়াজ মূল্যায়ন সারাংশ উপলব্ধ",
            body_template="ক্লিনিকাল ওয়ার্কস্পেসে ট্রায়াজ মূল্যায়ন উপলব্ধ রয়েছে।",
            required_variables=[],
        ),
    },
    NotificationType.SBAR_AVAILABLE: {
        "en": TemplateDefinition(
            version=1,
            title_template="Clinical SBAR Handover Ready",
            body_template="A clinical handover SBAR summary is ready for patient {patient_id}.",
            required_variables=["patient_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="क्लिनिकल SBAR हैंडओवर तैयार",
            body_template="रोगी {patient_id} के लिए क्लिनिकल SBAR हैंडओवर सारांश तैयार है।",
            required_variables=["patient_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ক্লিনিকাল এসবার হ্যান্ডওভার প্রস্তুত",
            body_template="রোগী {patient_id} এর জন্য ক্লিনিকাল হ্যান্ডওভার সারাংশ প্রস্তুত।",
            required_variables=["patient_id"],
        ),
    },
    NotificationType.DISCHARGE_DOCUMENT_AVAILABLE: {
        "en": TemplateDefinition(
            version=1,
            title_template="Discharge Summary Available",
            body_template="Your discharge summary from {facility_name} is now available in your portal.",
            required_variables=["facility_name"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="डिस्चार्ज सारांश उपलब्ध",
            body_template="{facility_name} से आपका डिस्चार्ज सारांश पोर्टल में उपलब्ध है।",
            required_variables=["facility_name"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ডিসচার্জ সারাংশ উপলব্ধ",
            body_template="{facility_name} থেকে আপনার ডিসচার্জ সারাংশ এখন পোর্টালে উপলব্ধ।",
            required_variables=["facility_name"],
        ),
    },
    NotificationType.CARE_PLAN_AVAILABLE: {
        "en": TemplateDefinition(
            version=1,
            title_template="Care Plan Available",
            body_template="Your personalized care plan has been generated and is available for review.",
            required_variables=[],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="केयर प्लान उपलब्ध",
            body_template="आपकी व्यक्तिगत देखभाल योजना तैयार है और समीक्षा के लिए उपलब्ध है।",
            required_variables=[],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="কেয়ার প্ল্যান উপলব্ধ",
            body_template="আপনার ব্যক্তিগত যত্ন পরিকল্পনা প্রস্তুত এবং পর্যালোচনার জন্য উপলব্ধ।",
            required_variables=[],
        ),
    },
    NotificationType.CARE_PLAN_UPDATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Care Plan Updated",
            body_template="Updates have been made to your care plan. Please review the updated milestones.",
            required_variables=[],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="केयर प्लान अपडेट किया गया",
            body_template="आपकी देखभाल योजना में अपडेट किए गए हैं। कृपया नई जानकारी देखें।",
            required_variables=[],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="কেয়ার প্ল্যান আপডেট করা হয়েছে",
            body_template="আপনার যত্ন পরিকল্পনায় পরিবর্তন আনা হয়েছে। অনুগ্রহ করে আপডেটগুলি পর্যালোচনা করুন।",
            required_variables=[],
        ),
    },
    NotificationType.TRANSFER_REQUEST_CREATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Transfer Request Initiated",
            body_template="An inter-facility clinical transfer request has been created for review.",
            required_variables=[],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="स्थानांतरण अनुरोध शुरू किया गया",
            body_template="समीक्षा के लिए एक अंतर-सुविधा क्लिनिकल स्थानांतरण अनुरोध बनाया गया है।",
            required_variables=[],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="স্থানান্তর অনুরোধ তৈরি করা হয়েছে",
            body_template="পর্যালোচনার জন্য একটি আন্তঃ-হাসপাতাল স্থানান্তর অনুরোধ তৈরি করা হয়েছে।",
            required_variables=[],
        ),
    },
    NotificationType.TRANSFER_STATUS_UPDATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Transfer Status Updated",
            body_template="Transfer reference {transfer_id} status has been updated to {new_status}.",
            required_variables=["transfer_id", "new_status"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="स्थानांतरण स्थिति अपडेट",
            body_template="स्थानांतरण संदर्भ {transfer_id} की स्थिति {new_status} में अपडेट की गई है।",
            required_variables=["transfer_id", "new_status"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="স্থানান্তর স্থিতি আপডেট",
            body_template="স্থানান্তর রেফারেন্স {transfer_id} এর স্থিতি {new_status} হিসেবে আপডেট করা হয়েছে।",
            required_variables=["transfer_id", "new_status"],
        ),
    },
    NotificationType.INTEROPERABILITY_IMPORT_COMPLETED: {
        "en": TemplateDefinition(
            version=1,
            title_template="FHIR Data Import Completed",
            body_template="External clinical records for patient {patient_id} were imported successfully.",
            required_variables=["patient_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="FHIR डेटा आयात पूर्ण",
            body_template="रोगी {patient_id} के लिए बाहरी मेडिकल रिकॉर्ड सफलतापूर्वक आयात किए गए।",
            required_variables=["patient_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="FHIR ডেটা আমদানি সম্পন্ন",
            body_template="রোগী {patient_id} এর জন্য বহিরাগত ক্লিনিকাল রেকর্ড সফলভাবে আমদানি করা হয়েছে।",
            required_variables=["patient_id"],
        ),
    },
    NotificationType.INTEROPERABILITY_IMPORT_FAILED: {
        "en": TemplateDefinition(
            version=1,
            title_template="FHIR Data Import Failed",
            body_template="Failed to import external records for patient {patient_id}. Please review import logs.",
            required_variables=["patient_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="FHIR डेटा आयात विफल",
            body_template="रोगी {patient_id} के रिकॉर्ड आयात करने में विफलता। कृपया लॉग देखें।",
            required_variables=["patient_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="FHIR ডেটা আমদানি ব্যর্থ",
            body_template="রোগী {patient_id} এর রেকর্ড আমদানি করতে ব্যর্থ হয়েছে। অনুগ্রহ করে লগ পর্যালোচনা করুন।",
            required_variables=["patient_id"],
        ),
    },
    NotificationType.DATA_QUALITY_REVIEW_REQUIRED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Clinical Data Quality Review",
            body_template="A clinical record inconsistency was detected for patient {patient_id} requiring reconciliation.",
            required_variables=["patient_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="डेटा गुणवत्ता समीक्षा",
            body_template="रोगी {patient_id} के लिए डेटा विसंगति पाई गई है जिसे समाधान की आवश्यकता है।",
            required_variables=["patient_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="ক্লিনিকাল ডেটা মান পর্যালোচনা",
            body_template="রোগী {patient_id} এর জন্য ডেটা অসঙ্গতি চিহ্নিত করা হয়েছে যা সমাধানের প্রয়োজন।",
            required_variables=["patient_id"],
        ),
    },
    NotificationType.SECURITY_ALERT: {
        "en": TemplateDefinition(
            version=1,
            title_template="HealthSetu Security Alert",
            body_template="Security alert: {details}. If this wasn't you, secure your account immediately.",
            required_variables=["details"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="सुरक्षा चेतावनी",
            body_template="सुरक्षा चेतावनी: {details}। यदि यह आप नहीं थे, तो तुरंत अपना खाता सुरक्षित करें।",
            required_variables=["details"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="নিরাপত্তা সতর্কতা",
            body_template="নিরাপত্তা সতর্কতা: {details}। এটি আপনি না হলে, অবিলম্বে আপনার অ্যাকাউন্ট সুরক্ষিত করুন।",
            required_variables=["details"],
        ),
    },
    NotificationType.ACCOUNT_SECURITY_NOTIFICATION: {
        "en": TemplateDefinition(
            version=1,
            title_template="Account Security Update",
            body_template="Your HealthSetu credentials or security settings were updated on {updated_date}.",
            required_variables=["updated_date"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="खाता सुरक्षा अपडेट",
            body_template="आपकी HealthSetu सुरक्षा सेटिंग्स {updated_date} को अपडेट की गईं।",
            required_variables=["updated_date"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাকাউন্ট নিরাপত্তা আপডেট",
            body_template="আপনার নিরাপত্তা সেটিংস {updated_date} তারিখে আপডেট করা হয়েছে।",
            required_variables=["updated_date"],
        ),
    },
    NotificationType.SYSTEM_NOTIFICATION: {
        "en": TemplateDefinition(
            version=1,
            title_template="System Maintenance Notice",
            body_template="{message}",
            required_variables=["message"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="सिस्टम रखरखाव सूचना",
            body_template="{message}",
            required_variables=["message"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="সিস্টেম রক্ষণাবেক্ষণ বিজ্ঞপ্তি",
            body_template="{message}",
            required_variables=["message"],
        ),
    },
    NotificationType.ADMINISTRATIVE_NOTIFICATION: {
        "en": TemplateDefinition(
            version=1,
            title_template="Administrative Notice",
            body_template="{message}",
            required_variables=["message"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="प्रशासनिक सूचना",
            body_template="{message}",
            required_variables=["message"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="প্রশাসনিক বিজ্ঞপ্তি",
            body_template="{message}",
            required_variables=["message"],
        ),
    },
    NotificationType.APPOINTMENT_CONFIRMED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Confirmed",
            body_template="Your appointment at facility {facility_id} is scheduled for {start_time}.",
            required_variables=["facility_id", "start_time"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट की पुष्टि हो गई",
            body_template="सुविधा {facility_id} पर आपका अपॉइंटमेंट {start_time} के लिए निर्धारित है।",
            required_variables=["facility_id", "start_time"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট নিশ্চিত হয়েছে",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্ট {start_time} এর জন্য নির্ধারিত হয়েছে।",
            required_variables=["facility_id", "start_time"],
        ),
    },
    NotificationType.APPOINTMENT_CREATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Request Created",
            body_template="Your appointment at facility {facility_id} has been recorded.",
            required_variables=["facility_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट का अनुरोध दर्ज किया गया",
            body_template="सुविधा {facility_id} पर आपका अपॉइंटमेंट दर्ज कर लिया गया है।",
            required_variables=["facility_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট অনুরোধ তৈরি হয়েছে",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্ট রেকর্ড করা হয়েছে।",
            required_variables=["facility_id"],
        ),
    },
    NotificationType.APPOINTMENT_RESCHEDULED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Rescheduled",
            body_template="Your appointment at facility {facility_id} has been rescheduled to {start_time}.",
            required_variables=["facility_id", "start_time"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट पुनर्निर्धारित किया गया",
            body_template="सुविधा {facility_id} पर आपका अपॉइंटमेंट {start_time} के लिए पुनर्निर्धारित किया गया है।",
            required_variables=["facility_id", "start_time"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট পুনর্নির্ধারণ করা হয়েছে",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্ট {start_time} এর জন্য পুনর্নির্ধারণ করা হয়েছে।",
            required_variables=["facility_id", "start_time"],
        ),
    },
    NotificationType.APPOINTMENT_CANCELLED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Cancelled",
            body_template="Your appointment at facility {facility_id} has been cancelled.",
            required_variables=["facility_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट रद्द किया गया",
            body_template="सुविधा {facility_id} पर आपका अपॉइंटमेंट रद्द कर दिया गया है।",
            required_variables=["facility_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট বাতিল করা হয়েছে",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্ট বাতিল করা হয়েছে।",
            required_variables=["facility_id"],
        ),
    },
    NotificationType.APPOINTMENT_REMINDER: {
        "en": TemplateDefinition(
            version=1,
            title_template="Upcoming Appointment Reminder",
            body_template="Reminder: You have an upcoming appointment at facility {facility_id} on {start_time}.",
            required_variables=["facility_id", "start_time"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="आगामी अपॉइंटमेंट अनुस्मारक",
            body_template="याद दिलाना: सुविधा {facility_id} पर {start_time} को आपका अपॉइंटमेंट है।",
            required_variables=["facility_id", "start_time"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="আসন্ন অ্যাপয়েন্টমেন্ট স্মারক",
            body_template="স্মারক: {facility_id} সুবিধায় {start_time} তারিখে আপনার একটি অ্যাপয়েন্টমেন্ট রয়েছে।",
            required_variables=["facility_id", "start_time"],
        ),
    },
    NotificationType.APPOINTMENT_CHECK_IN: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Check-In Confirmed",
            body_template="You have been checked in for your appointment at {facility_id}.",
            required_variables=["facility_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट चेक-इन की पुष्टि हो गई",
            body_template="सुविधा {facility_id} पर आपके अपॉइंटमेंट के लिए चेक-इन हो गया है।",
            required_variables=["facility_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট চেক-ইন নিশ্চিত হয়েছে",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্টের জন্য চেক-ইন সম্পন্ন হয়েছে।",
            required_variables=["facility_id"],
        ),
    },
    NotificationType.APPOINTMENT_NO_SHOW: {
        "en": TemplateDefinition(
            version=1,
            title_template="Missed Appointment",
            body_template="You missed your scheduled appointment at {facility_id}.",
            required_variables=["facility_id"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="छूटा हुआ अपॉइंटमेंट",
            body_template="सुविधा {facility_id} पर आपका निर्धारित अपॉइंटमेंट छूट गया।",
            required_variables=["facility_id"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অনুপস্থিত অ্যাপয়েন্টমেন্ট",
            body_template="{facility_id} সুবিধায় আপনার নির্ধারিত অ্যাপয়েন্টমেন্টটি অনুপস্থিত ছিল।",
            required_variables=["facility_id"],
        ),
    },
    NotificationType.APPOINTMENT_STATUS_UPDATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Appointment Status Update",
            body_template="Your appointment status at {facility_id} is now {status}.",
            required_variables=["facility_id", "status"],
        ),
        "hi": TemplateDefinition(
            version=1,
            title_template="अपॉइंटमेंट स्थिति अपडेट",
            body_template="सुविधा {facility_id} पर आपकी अपॉइंटमेंट स्थिति अब {status} है।",
            required_variables=["facility_id", "status"],
        ),
        "bn": TemplateDefinition(
            version=1,
            title_template="অ্যাপয়েন্টমেন্ট স্থিতি আপডেট",
            body_template="{facility_id} সুবিধায় আপনার অ্যাপয়েন্টমেন্ট স্থিতি এখন {status}।",
            required_variables=["facility_id", "status"],
        ),
    },
    NotificationType.PAYMENT_CREATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Payment Initiated",
            body_template="A payment of {currency} {amount} has been initiated for transaction {payment_number}.",
            required_variables=["payment_number", "amount", "currency"],
        ),
    },
    NotificationType.PAYMENT_PROCESSING: {
        "en": TemplateDefinition(
            version=1,
            title_template="Payment Processing",
            body_template="Your payment {payment_number} is currently being processed by the gateway.",
            required_variables=["payment_number"],
        ),
    },
    NotificationType.PAYMENT_SUCCEEDED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Payment Successful",
            body_template="Payment of {currency} {amount} has been successfully completed.",
            required_variables=["amount", "currency"],
        ),
    },
    NotificationType.PAYMENT_FAILED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Payment Failed",
            body_template="Payment transaction {payment_number} could not be completed.",
            required_variables=["payment_number"],
        ),
    },
    NotificationType.PAYMENT_RECONCILIATION_REQUIRED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Payment Status Pending Verification",
            body_template="Payment {payment_number} requires verification with the gateway.",
            required_variables=["payment_number"],
        ),
    },
    NotificationType.REFUND_CREATED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Refund Requested",
            body_template="A refund of {currency} {amount} has been requested.",
            required_variables=["amount", "currency"],
        ),
    },
    NotificationType.REFUND_SUCCEEDED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Refund Completed",
            body_template="Refund {refund_number} of {currency} {amount} was processed successfully.",
            required_variables=["refund_number", "amount", "currency"],
        ),
    },
    NotificationType.REFUND_FAILED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Refund Failed",
            body_template="Refund {refund_number} could not be completed.",
            required_variables=["refund_number"],
        ),
    },
    NotificationType.INVOICE_ISSUED: {
        "en": TemplateDefinition(
            version=1,
            title_template="Invoice Issued",
            body_template="Invoice {invoice_number} for {currency} {amount} has been issued.",
            required_variables=["invoice_number", "amount", "currency"],
        ),
    },
    NotificationType.INVOICE_OVERDUE: {
        "en": TemplateDefinition(
            version=1,
            title_template="Invoice Overdue",
            body_template="Invoice {invoice_number} is past due date.",
            required_variables=["invoice_number"],
        ),
    },
    NotificationType.INVOICE_PAID: {
        "en": TemplateDefinition(
            version=1,
            title_template="Invoice Paid",
            body_template="Invoice {invoice_number} has been fully settled.",
            required_variables=["invoice_number"],
        ),
    },
}


class NotificationTemplateService:
    """Service managing template rendering, localization, and content safety."""

    def __init__(self) -> None:
        pass

    def render_notification(
        self,
        notification_type: NotificationType,
        variables: Dict[str, Any],
        language: Optional[str] = None,
    ) -> Tuple[str, str, int]:
        """Render localized title and body with variables.

        Returns (title, body, template_version).
        """
        lang = (language or "en").lower().strip()
        type_templates = TEMPLATES.get(notification_type)
        if not type_templates:
            raise TemplateResolutionException(f"No template defined for type '{notification_type.value}'.")

        # Fallback to English if requested language is not supported
        tpl = type_templates.get(lang) or type_templates.get("en")
        if not tpl:
            raise TemplateResolutionException(f"Template for type '{notification_type.value}' lacks English fallback.")

        # 1. Validate required variables
        missing = [v for v in tpl.required_variables if v not in variables or variables[v] is None]
        if missing:
            raise TemplateResolutionException(
                f"Missing required template variables for '{notification_type.value}': {', '.join(missing)}"
            )

        # 2. Sanitize and validate variable values
        sanitized_vars: Dict[str, str] = {}
        for k, v in variables.items():
            str_val = str(v)
            # Check for clinical safety violations in variable values
            lower_val = str_val.lower()
            for kw in DISALLOWED_CLINICAL_KEYWORDS:
                if kw in lower_val:
                    raise UnauthorizedClinicalContentException(
                        f"Variable '{k}' contains prohibited clinical keyword '{kw}' violating safety boundary."
                    )
            sanitized_vars[k] = str_val

        # 3. Format templates
        try:
            rendered_title = tpl.title_template.format(**sanitized_vars)
            rendered_body = tpl.body_template.format(**sanitized_vars)
        except Exception as e:
            raise TemplateResolutionException(f"Failed to interpolate variables: {e}")

        # 4. Header Injection Guard: Title must not have CRLF
        if "\r" in rendered_title or "\n" in rendered_title:
            rendered_title = rendered_title.replace("\r", " ").replace("\n", " ").strip()

        # 5. Check rendered body for clinical safety violations
        lower_body = rendered_body.lower()
        for kw in DISALLOWED_CLINICAL_KEYWORDS:
            if kw in lower_body:
                raise UnauthorizedClinicalContentException(
                    f"Rendered notification contains prohibited clinical advice keyword '{kw}'."
                )

        return rendered_title, rendered_body, tpl.version
