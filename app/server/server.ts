import { createApp, analytics, genie, lakebase, server } from '@databricks/appkit';
import { registerWorkflowRoutes } from './interventions';

const genieSpaceId = process.env.DATABRICKS_GENIE_SPACE_ID;

if (!genieSpaceId) {
  throw new Error('DATABRICKS_GENIE_SPACE_ID is required');
}

createApp({
  plugins: [analytics(), genie({ spaces: { default: genieSpaceId } }), lakebase(), server()],
  async onPluginsReady(appkit) {
    try {
      await appkit.lakebase.query('CREATE SCHEMA IF NOT EXISTS student_retention_app');
      console.log('[lakebase] student_retention_app schema is available');
    } catch (error) {
      console.warn('[lakebase] schema bootstrap deferred:', error);
    }

    appkit.server.extend((app) => {
      registerWorkflowRoutes(app, appkit.lakebase);
      app.get('/api/whoami', (req, res) => {
        res.json({
          email: req.header('x-forwarded-email') ?? null,
          user: req.header('x-forwarded-user') ?? null,
          genieExecution: 'on_behalf_of_user',
        });
      });
    });
  },
}).catch(console.error);
