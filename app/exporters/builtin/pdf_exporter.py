"""PDF report exporter plugin."""

from __future__ import annotations

import base64
import io
from typing import TYPE_CHECKING

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Flowable, Image, Paragraph, SimpleDocTemplate, Spacer

from app.exporters.base import Exporter, ExportResult, exporter_registry

if TYPE_CHECKING:
    from app.plots.base import PlotResult
    from app.stats.base import StatResult


@exporter_registry.register("pdf")
class PdfExporter(Exporter):
    """Exporter that compiles evaluation results and plots into a PDF report."""

    @property
    def name(self) -> str:
        """Return the unique name of the exporter."""
        return "pdf"

    @property
    def content_type(self) -> str:
        """Return the default content type of the exporter."""
        return "application/pdf"

    def export(
        self,
        stat_result: StatResult | None,
        plots: list[PlotResult],
        df: pd.DataFrame,
    ) -> ExportResult:
        """Export session results and plots to a PDF report.

        Args:
            stat_result: The statistical test result.
            plots: The list of plot results.
            df: The dataset DataFrame.

        Returns:
            An ExportResult containing the PDF bytes.
        """
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        story: list[Flowable] = []
        styles = getSampleStyleSheet()

        # Title
        story.append(Paragraph("Experiment Evaluation Report", styles["Title"]))
        story.append(Spacer(1, 15))

        # Dataset summary
        story.append(Paragraph("Dataset Summary", styles["Heading2"]))
        n_rows = len(df)
        n_cols = len(df.columns)
        story.append(
            Paragraph(
                f"<b>Total Rows:</b> {n_rows}<br/><b>Total Columns:</b> {n_cols}",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 15))

        # Statistical analysis results
        if stat_result is not None:
            story.append(Paragraph("Statistical Analysis Results", styles["Heading2"]))
            story.append(
                Paragraph(
                    f"<b>Method:</b> {stat_result.method_name}",
                    styles["BodyText"],
                )
            )
            story.append(
                Paragraph(
                    f"<b>Test Statistic:</b> {stat_result.test_statistic:.4f}",
                    styles["BodyText"],
                )
            )
            story.append(
                Paragraph(
                    f"<b>p-value:</b> {stat_result.p_value:.4f}",
                    styles["BodyText"],
                )
            )
            if stat_result.effect_size is not None:
                story.append(
                    Paragraph(
                        f"<b>Effect Size:</b> {stat_result.effect_size:.4f}",
                        styles["BodyText"],
                    )
                )
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Summary:</b>", styles["BodyText"]))
            story.append(Paragraph(stat_result.summary, styles["BodyText"]))
            story.append(Spacer(1, 15))

        # Visualizations
        if plots:
            story.append(Paragraph("Visualizations", styles["Heading2"]))
            story.append(Spacer(1, 10))
            for p in plots:
                img_bytes = base64.b64decode(p.image_base64)
                img_buf = io.BytesIO(img_bytes)
                # Render the image inside the PDF report (400x300 size is reasonable)
                story.append(Image(img_buf, width=400, height=300))
                story.append(Spacer(1, 15))

        doc.build(story)
        buf.seek(0)
        content_bytes = buf.read()

        return ExportResult(
            content=content_bytes,
            content_type=self.content_type,
            filename="evaluation_report.pdf",
        )
