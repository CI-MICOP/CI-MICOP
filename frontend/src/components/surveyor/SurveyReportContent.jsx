import { formatCurrency, formatDate } from "../../utils/format";
import { captureMethodText, deviceTimeText, locationStatusText, locationText, serverTimeText } from "./captureDisplay";
import { SubmissionReviewNotice } from "./WorkflowNotices";

// Renders the survey report returned by GET /surveyor/claims/{id}/report.
// The PDF download is built by the backend from the same data, so the two
// always agree. Missing values are shown as "Not available", never guessed.
const NOT_AVAILABLE = "Not available";

function show(value) {
  if (value === null || value === undefined || value === "") return NOT_AVAILABLE;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

const showDate = (value) => (value ? formatDate(value) : NOT_AVAILABLE);
const showMoney = (value) => (value === null || value === undefined ? NOT_AVAILABLE : formatCurrency(value));
const showTime = (value) => (value ? String(value).slice(0, 5) : NOT_AVAILABLE);

function analysisSummary(analysis) {
  if (!analysis) return "Not analysed yet";
  return [
    `Image quality ${analysis.Image_Quality}`,
    `Damage detected: ${show(analysis.Vehicle_Damage_Detected)}`,
    `Severity: ${analysis.Damage_Severity}`,
    `Location match: ${show(analysis.Location_Match)}`,
    `Duplicate: ${show(analysis.Duplicate_Evidence_Indicator)}`,
    `Confidence ${analysis.Evidence_Confidence_Score}`,
  ].join(" · ");
}

export default function SurveyReportContent({ report }) {
  const { claim, inspection } = report;
  const customer = report.customer ?? {};
  const vehicle = report.vehicle ?? {};
  const policy = report.policy ?? {};
  const invalidFields = new Set(report.invalid_values.map((item) => item.field));

  const finding = (field) =>
    invalidFields.has(field) ? (
      <>
        {show(inspection[field])} <span className="text-xs text-warning">(not a valid option)</span>
      </>
    ) : (
      show(inspection[field])
    );

  return (
    <div className="space-y-5">
      <SubmissionReviewNotice review={report.submission_review} />
      <Section title="A. Claim Information">
        <Fields
          items={[
            ["Claim ID", show(claim.Claim_ID)],
            ["Claim Number", show(claim.Claim_Number)],
            ["Claim Date", showDate(claim.Claim_Date)],
            ["Intimation Date", showDate(claim.Claim_Intimation_Date)],
            ["Claim Type", show(claim.Claim_Type)],
            ["Claim Status", show(claim.Claim_Status)],
            ["Claim Amount", showMoney(claim.Claim_Amount)],
            ["Customer Name", show(customer.Customer_Name)],
            ["Customer ID", show(customer.Customer_ID)],
            ["Vehicle Registration", show(vehicle.Registration_Number)],
            ["Vehicle Make / Model", `${show(vehicle.Make)} / ${show(vehicle.Model)}`],
            ["Vehicle Year", show(vehicle.Manufacturing_Year)],
            ["Policy Number", show(policy.Policy_Number)],
            ["Policy Type", show(policy.Policy_Type)],
          ]}
        />
        <Fields className="mt-3" wide items={[["Claim Description", show(claim.Claim_Description)]]} />
      </Section>

      <Section title="B. Accident Information">
        {report.accidents.length === 0 ? (
          <p className="text-sm text-muted">No accident record is stored for this claim.</p>
        ) : (
          report.accidents.map((accident, index) => (
            <div key={index} className={index > 0 ? "mt-4 border-t border-border pt-4" : ""}>
              {report.accidents.length > 1 && <h4 className="mb-2 text-sm font-semibold text-ink">Accident {index + 1}</h4>}
              <Fields
                items={[
                  ["Date and Time", `${showDate(accident.Accident_Date)}, ${showTime(accident.Accident_Time)}`],
                  ["Accident Type", show(accident.Accident_Type)],
                  ["Location", show(accident.Accident_Location)],
                  ["City / State / Pincode", `${show(accident.Accident_City)} / ${show(accident.Accident_State)} / ${show(accident.Accident_Pincode)}`],
                  ["Weather / Road", `${show(accident.Weather_Condition)} / ${show(accident.Road_Condition)}`],
                  ["Police Report", show(accident.Police_Report_Available)],
                  ["FIR Number", show(accident.FIR_Number)],
                  ["Third Party Involved", show(accident.Third_Party_Involved)],
                  ["Injury Reported", show(accident.Injury_Reported)],
                  ["Witness Available", show(accident.Witness_Available)],
                ]}
              />
              <Fields className="mt-3" wide items={[["Description", show(accident.Accident_Description)]]} />
            </div>
          ))
        )}
      </Section>

      <Section title="C. Inspection Details">
        <Fields
          items={[
            ["Inspection ID", show(inspection.Inspection_ID)],
            ["Inspection Date", showDate(inspection.Inspection_Date)],
            ["Inspection Location", show(inspection.Inspection_Location)],
            ["Vehicle Condition", finding("Vehicle_Condition")],
            ["Damage Observed", finding("Damage_Observed")],
            ["Damage Severity", inspection.Damage_Observed === "Yes" ? finding("Damage_Severity") : "Not applicable"],
            ["Parts Required", show(inspection.Parts_Required)],
            ["Repair Recommendation", finding("Repair_Recommendation")],
            ["Inspection Status", show(inspection.Inspection_Status)],
          ]}
        />
        <Fields className="mt-3" wide items={[["Surveyor Comments", show(inspection.Surveyor_Comments)]]} />
        {report.invalid_values.length > 0 && (
          <p className="mt-3 text-xs text-warning">
            Stored value(s) not among the allowed options: {report.invalid_values.map((item) => item.label).join(", ")}.
            Shown as stored.
          </p>
        )}
      </Section>

      <Section title="D. Vehicle Damage Assessment">
        {report.vehicle_damage.length === 0 ? (
          <p className="text-sm text-muted">No vehicle damage records have been saved for this claim.</p>
        ) : (
          <>
            <div className="space-y-3">
              {report.vehicle_damage.map((damage, index) => (
                <Record key={damage.Damage_ID} title={`Damage ${index + 1}: ${show(damage.Damaged_Part)}`}>
                  <Fields
                    items={[
                      ["Damage Type", show(damage.Damage_Type)],
                      ["Severity", show(damage.Damage_Severity)],
                      ["Location", show(damage.Damage_Location)],
                      ["Repair or Replace", show(damage.Repair_or_Replace)],
                      ["Estimated Cost", showMoney(damage.Estimated_Damage_Cost)],
                      ["Photo Evidence Available", show(damage.Photo_Evidence_Available)],
                    ]}
                  />
                  <Fields className="mt-3" wide items={[["Description", show(damage.Damage_Description)]]} />
                </Record>
              ))}
            </div>
            <p className="mt-3 text-sm text-ink">
              <span className="font-medium">Total estimated damage cost:</span> {showMoney(report.total_estimated_damage_cost)}
            </p>
          </>
        )}
      </Section>

      <Section title="E. Evidence and Capture Metadata">
        {report.evidence.length === 0 ? (
          <p className="text-sm text-muted">No evidence has been saved for this claim.</p>
        ) : (
          <div className="space-y-3">
            {report.evidence.map((item, index) => (
              <Record key={item.Evidence_ID} title={`Evidence ${index + 1}: ${show(item.File_Name)}`}>
                <Fields
                  items={[
                    ["Evidence Type", show(item.Evidence_Type)],
                    ["Evidence Date", showDate(item.Evidence_Date)],
                    ["Source", show(item.Evidence_Source)],
                    ["Capture Method", captureMethodText(item.capture)],
                    ["Device-reported Capture Time", deviceTimeText(item.capture)],
                    ["Device-reported Location", locationText(item.capture)],
                    ["Location Check (server)", locationStatusText(item.capture)],
                    ["Server Receipt Time", serverTimeText(item.capture)],
                    ["Counts as Surveyor Photo", item.qualifying_capture ? "Yes" : "No"],
                    ["AI Verification Status", show(item.Verification_Status)],
                  ]}
                />
                <Fields className="mt-3" wide items={[["Automated Analysis (AI)", analysisSummary(item.analysis)]]} />
              </Record>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-muted">
          Device-reported time and location are recorded and checked for plausibility; they are not proof of where or
          when a photo was taken.
        </p>
      </Section>

      <Section title="F. Surveyor">
        <Fields items={[["Surveyor Employee ID", show(report.surveyor?.Employee_ID)]]} />
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="rounded-card border border-border bg-card p-5 print:break-inside-avoid print:border-0 print:p-0">
      <h3 className="mb-4 border-b border-brand-100 pb-2 text-sm font-semibold text-brand-700">{title}</h3>
      {children}
    </section>
  );
}

function Record({ title, children }) {
  return (
    <div className="rounded-lg border-l-2 border-brand-300 bg-surface p-3 print:break-inside-avoid">
      <h4 className="mb-2 text-sm font-semibold text-ink">{title}</h4>
      {children}
    </div>
  );
}

function Fields({ items, wide = false, className = "" }) {
  return (
    <dl className={`grid grid-cols-1 gap-x-6 gap-y-3 ${wide ? "" : "sm:grid-cols-2"} ${className}`}>
      {items.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs font-medium uppercase tracking-wide text-muted">{label}</dt>
          <dd className="mt-0.5 break-words text-sm text-ink">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
