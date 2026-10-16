{{- define "cv.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "cv.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "cv.labels" -}}
app.kubernetes.io/name: {{ include "cv.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "cv.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cv.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
