"""CSV rendering shared by owner exports (Excel-compatible UTF-8 BOM)."""
import csv
import io

from fastapi.responses import Response


def csv_response(filename, headers, rows):
    def cell(value):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        if isinstance(value, str) and value.startswith(('\t', '\r', '\n')):
            return "'" + value
        return value

    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([cell(value) for value in row])
    return Response(output.getvalue().encode('utf-8-sig'), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
    })
