import Button from '../../../../components/ui/Button.jsx'
import Card from '../../../../components/ui/Card.jsx'
import Input from '../../../../components/ui/Input.jsx'
import Textarea from '../../../../components/ui/Textarea.jsx'
import { DESIGN_PLANNING_NODE_IDS } from '../constants/workflow.js'

export default function TechnicalPlanningPanel({
  input = {},
  errors = {},
  onUpdateField,
  onNavigate,
  onValidate,
}) {
  function handleContinue() {
    const isValid = onValidate ? onValidate() : true
    if (isValid && onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.OUTPUT_SELECTION)
    }
  }

  function handleBack() {
    if (onNavigate) {
      onNavigate(DESIGN_PLANNING_NODE_IDS.PROJECT_SPECIFICATIONS)
    }
  }

  return (
    <div className="space-y-6" data-testid="agent2-panel-TECHNICAL_PLANNING">
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Technical preferences card */}
        <Card className="border-default bg-[#150c2a] p-6 space-y-4">
          <div>
            <h3 className="text-card-heading font-semibold text-content-primary">
              Technical preferences
            </h3>
            <p className="mt-1 text-sm text-content-muted">
              Optional design constraints.
            </p>
          </div>
          <div className="space-y-4">
            <Input
              label="Preferred Technology Stack"
              value={input.preferred_technology_stack || ''}
              onChange={(e) => onUpdateField?.('preferred_technology_stack', e.target.value)}
              placeholder="e.g. React 19, FastAPI, PostgreSQL"
              inputClassName="bg-[#0b0517] border-default"
            />
            <Textarea
              label="Technical Constraints"
              rows={3}
              value={input.technical_constraints || ''}
              onChange={(e) => onUpdateField?.('technical_constraints', e.target.value)}
              placeholder="e.g. Must run on Linux ARM64, response time < 200ms"
              textareaClassName="bg-[#0b0517] border-default"
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Deployment Preference"
                value={input.deployment_preference || ''}
                onChange={(e) => onUpdateField?.('deployment_preference', e.target.value)}
                placeholder="e.g. Docker, AWS ECS"
                inputClassName="bg-[#0b0517] border-default"
              />
              <Input
                label="Database Preference"
                value={input.database_preference || ''}
                onChange={(e) => onUpdateField?.('database_preference', e.target.value)}
                placeholder="e.g. PostgreSQL 16"
                inputClassName="bg-[#0b0517] border-default"
              />
            </div>
            <Textarea
              label="UI/UX Constraints"
              rows={3}
              value={input.ui_ux_constraints || ''}
              onChange={(e) => onUpdateField?.('ui_ux_constraints', e.target.value)}
              placeholder="e.g. Responsive dark theme, WCAG 2.1 AA compliant"
              textareaClassName="bg-[#0b0517] border-default"
            />
            <Textarea
              label="Architecture Notes"
              rows={3}
              value={input.architecture_notes || ''}
              onChange={(e) => onUpdateField?.('architecture_notes', e.target.value)}
              placeholder="e.g. Clean architecture, modular monolith"
              textareaClassName="bg-[#0b0517] border-default"
            />
          </div>
        </Card>

        {/* Planning inputs card */}
        <Card className="border-default bg-[#150c2a] p-6 space-y-4">
          <div>
            <h3 className="text-card-heading font-semibold text-content-primary">
              Planning inputs
            </h3>
            <p className="mt-1 text-sm text-content-muted">
              Used by sprint and assignment outputs.
            </p>
          </div>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Input
                label="Development team count"
                type="number"
                min="1"
                value={input.development_team_count || ''}
                error={errors.development_team_count}
                onChange={(e) => onUpdateField?.('development_team_count', e.target.value)}
                placeholder="Team count"
                inputClassName="bg-[#0b0517] border-default"
              />
              <Input
                label="Sprint duration (days)"
                type="number"
                min="1"
                value={input.sprint_duration || ''}
                error={errors.sprint_duration}
                onChange={(e) => onUpdateField?.('sprint_duration', e.target.value)}
                placeholder="Sprint duration"
                inputClassName="bg-[#0b0517] border-default"
              />
              <Input
                label="Expected project duration"
                value={input.expected_project_duration || ''}
                onChange={(e) => onUpdateField?.('expected_project_duration', e.target.value)}
                placeholder="Expected duration"
                inputClassName="bg-[#0b0517] border-default"
              />
            </div>
            <Textarea
              label="Developer Roles"
              rows={3}
              value={input.developer_roles || ''}
              onChange={(e) => onUpdateField?.('developer_roles', e.target.value)}
              placeholder="e.g. 2 Frontend, 2 Backend, 1 QA"
              textareaClassName="bg-[#0b0517] border-default"
            />
            <Textarea
              label="Developer Skills"
              rows={3}
              value={input.developer_skills || ''}
              onChange={(e) => onUpdateField?.('developer_skills', e.target.value)}
              placeholder="e.g. React, Python, FastAPI, Docker"
              textareaClassName="bg-[#0b0517] border-default"
            />
            <Textarea
              label="Team Composition"
              rows={3}
              value={input.team_composition || ''}
              onChange={(e) => onUpdateField?.('team_composition', e.target.value)}
              placeholder="e.g. Cross-functional agile team"
              textareaClassName="bg-[#0b0517] border-default"
            />
          </div>
        </Card>
      </div>

      {/* Conditional validation callout card */}
      <Card className="border-default bg-[#150c2a] p-6">
        <h3 className="text-card-heading font-semibold text-content-primary">
          Conditional validation
        </h3>
        <p className="mt-1 text-sm text-content-muted">
          Planning data is checked before Agent2Engine runs.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-content-secondary">
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">SPRINT_PLAN</code> requires development_team_count + sprint_duration
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">TASK_ASSIGNMENT</code> requires development_team_count
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-content-muted" aria-hidden="true">•</span>
            <span>
              <code className="text-xs font-semibold text-content-primary">JIRA_PLAN</code> requires development_team_count
            </span>
          </li>
        </ul>
      </Card>

      {/* Footer navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-default/60 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={handleBack}
          className="border-default bg-[#170c2c] text-content-primary hover:bg-[#20103c]"
        >
          Back — Project & Specifications
        </Button>
        <Button
          type="button"
          variant="primary"
          onClick={handleContinue}
        >
          Next — Output Selection
        </Button>
      </div>
    </div>
  )
}
