{{/*
Expand the name of the chart.
*/}}
{{- define "algobattle.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a fully qualified app name.
*/}}
{{- define "algobattle.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Common labels — applied to every resource.
*/}}
{{- define "algobattle.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "algobattle.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: algobattle
{{- end -}}

{{/*
Selector labels — used for matching pods to services.
*/}}
{{- define "algobattle.selectorLabels" -}}
app.kubernetes.io/name: {{ include "algobattle.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Component selector labels — for individual workloads.
Usage: include "algobattle.componentSelector" (dict "ctx" . "component" "api")
*/}}
{{- define "algobattle.componentSelector" -}}
{{- $ctx := .ctx -}}
{{- $component := .component -}}
app.kubernetes.io/component: {{ $component }}
app.kubernetes.io/name: {{ include "algobattle.name" $ctx }}
app.kubernetes.io/instance: {{ $ctx.Release.Name }}
{{- end -}}

{{/*
Component labels.
Usage: include "algobattle.componentLabels" (dict "ctx" . "component" "api")
*/}}
{{- define "algobattle.componentLabels" -}}
{{- $ctx := .ctx -}}
{{- $component := .component -}}
{{ include "algobattle.labels" $ctx }}
app.kubernetes.io/component: {{ $component }}
{{- end -}}

{{/*
Image reference — registry/repo:tag.
Usage: include "algobattle.image" (dict "image" .Values.api.image "defaultTag" .Chart.AppVersion)
*/}}
{{- define "algobattle.image" -}}
{{- $img := .image -}}
{{- $defaultTag := .defaultTag -}}
{{- if hasKey $img "registry" -}}
{{- printf "%s/%s:%s" $img.registry $img.repository ($img.tag | default $defaultTag) -}}
{{- else -}}
{{- $img -}}
{{- end -}}
{{- end -}}

{{/*
Secret name helper.
*/}}
{{- define "algobattle.secretName" -}}
{{- default (printf "%s-secrets" (include "algobattle.fullname" .)) .Values.existingSecret -}}
{{- end -}}

{{/*
Database URL — built from postgres credentials.
*/}}
{{- define "algobattle.databaseUrl" -}}
{{- $host := "" -}}
{{- if .Values.postgres.useExternal -}}
{{- $host = .Values.postgres.external.host -}}
{{- else -}}
{{- $host = printf "%s-postgres" (include "algobattle.fullname" .) -}}
{{- end -}}
postgresql+asyncpg://{{ .Values.postgres.auth.usernameKey | required "postgres username" }}:$(DATABASE_PASSWORD)@{{ $host }}:{{ .Values.postgres.external.port | default 5432 }}/{{ .Values.postgres.external.database | default "algobattle" }}
{{- end -}}

{{/*
Redis URL.
*/}}
{{- define "algobattle.redisUrl" -}}
redis://:$(REDIS_PASSWORD)@{{ include "algobattle.fullname" . }}-redis:{{ .Values.redis.port | default 6379 }}/0
{{- end -}}