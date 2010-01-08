from django.conf import settings
from django.utils.translation import ugettext_lazy as _

ALLOW_COMMENTS_DEFAULT = 1
ALLOW_COMMENTS_TRUE    = 2
ALLOW_COMMENTS_FALSE   = 3
ALLOW_COMMENTS_CHOICES = (
    (ALLOW_COMMENTS_DEFAULT, _(u"Default")),
    (ALLOW_COMMENTS_TRUE,    _(u"Yes")),
    (ALLOW_COMMENTS_FALSE,   _(u"No")),
)

LANGUAGE_CHOICES = [("0", _(u"Neutral"),)]
LANGUAGE_CHOICES.extend(settings.LANGUAGES)