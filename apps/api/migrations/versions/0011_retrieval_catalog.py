"""검색기 설정·구축 세대·활성 release 계보를 독립적으로 기록한다.

Revision ID: 0011
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_CAPABILITY_KEY = "schema.retrieval_catalog_v1"


def upgrade() -> None:
    statements = [
        """
        CREATE TABLE corpus_snapshots (
          snapshot_id text PRIMARY KEY,
          fingerprint_sha256 text NOT NULL UNIQUE
            CHECK(fingerprint_sha256 ~ '^[0-9a-f]{64}$'),
          parser_schema_version text NOT NULL,
          supported_as_of_from date NOT NULL,
          supported_as_of_through date NOT NULL,
          document_count integer NOT NULL CHECK(document_count>=0),
          provision_count integer NOT NULL CHECK(provision_count>=0),
          created_at timestamptz NOT NULL DEFAULT now(),
          CHECK(supported_as_of_from<=supported_as_of_through)
        )
        """,
        """
        CREATE TABLE retrieval_profiles (
          profile_key text PRIMARY KEY,
          retriever_kind text NOT NULL CHECK(length(retriever_kind)>0),
          engine text NOT NULL CHECK(length(engine)>0),
          implementation_version text NOT NULL CHECK(length(implementation_version)>0),
          configuration jsonb NOT NULL
            CHECK(jsonb_typeof(configuration)='object'),
          configuration_sha256 text NOT NULL
            CHECK(configuration_sha256 ~ '^[0-9a-f]{64}$'),
          embedding_profile_key text REFERENCES embedding_profiles(profile_key),
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(
            retriever_kind,engine,implementation_version,configuration_sha256
          )
        )
        """,
        """
        CREATE TABLE retrieval_index_builds (
          build_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          snapshot_id text NOT NULL REFERENCES corpus_snapshots(snapshot_id),
          profile_key text NOT NULL REFERENCES retrieval_profiles(profile_key),
          state text NOT NULL
            CHECK(state IN ('building','ready','failed','superseded')),
          expected_count integer NOT NULL CHECK(expected_count>=0),
          indexed_count integer NOT NULL CHECK(indexed_count>=0),
          artifact_fingerprint_sha256 text
            CHECK(
              artifact_fingerprint_sha256 IS NULL
              OR artifact_fingerprint_sha256 ~ '^[0-9a-f]{64}$'
            ),
          build_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
            CHECK(jsonb_typeof(build_metadata)='object'),
          error_code text,
          started_at timestamptz NOT NULL DEFAULT now(),
          finished_at timestamptz,
          CHECK(indexed_count<=expected_count),
          CHECK(
            (state='building' AND finished_at IS NULL)
            OR (state<>'building' AND finished_at IS NOT NULL)
          ),
          CHECK(
            state NOT IN ('ready','superseded')
            OR (
              indexed_count=expected_count
              AND artifact_fingerprint_sha256 IS NOT NULL
            )
          ),
          CHECK((state='failed')=(error_code IS NOT NULL)),
          UNIQUE(build_id,profile_key,snapshot_id)
        )
        """,
        """
        CREATE TABLE retrieval_configurations (
          configuration_key text PRIMARY KEY,
          strategy text NOT NULL CHECK(length(strategy)>0),
          configuration_version text NOT NULL CHECK(length(configuration_version)>0),
          parameters jsonb NOT NULL CHECK(jsonb_typeof(parameters)='object'),
          parameters_sha256 text NOT NULL
            CHECK(parameters_sha256 ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE(strategy,configuration_version,parameters_sha256)
        )
        """,
        """
        CREATE TABLE retrieval_configuration_members (
          configuration_key text NOT NULL
            REFERENCES retrieval_configurations(configuration_key) ON DELETE CASCADE,
          profile_key text NOT NULL REFERENCES retrieval_profiles(profile_key),
          role text NOT NULL CHECK(length(role)>0),
          ordinal integer NOT NULL CHECK(ordinal>=0),
          required boolean NOT NULL,
          PRIMARY KEY(configuration_key,profile_key),
          UNIQUE(configuration_key,ordinal)
        )
        """,
        """
        CREATE TABLE retrieval_releases (
          release_key text PRIMARY KEY,
          snapshot_id text NOT NULL REFERENCES corpus_snapshots(snapshot_id),
          configuration_key text NOT NULL
            REFERENCES retrieval_configurations(configuration_key),
          state text NOT NULL CHECK(state IN ('draft','ready','retired')),
          manifest_sha256 text NOT NULL
            CHECK(manifest_sha256 ~ '^[0-9a-f]{64}$'),
          created_at timestamptz NOT NULL DEFAULT now(),
          ready_at timestamptz,
          CHECK(
            (state='draft' AND ready_at IS NULL)
            OR (state IN ('ready','retired') AND ready_at IS NOT NULL)
          ),
          UNIQUE(release_key,configuration_key,snapshot_id),
          UNIQUE(release_key,snapshot_id),
          UNIQUE(release_key,state)
        )
        """,
        """
        CREATE TABLE retrieval_release_builds (
          release_key text NOT NULL,
          configuration_key text NOT NULL,
          snapshot_id text NOT NULL,
          profile_key text NOT NULL,
          build_id uuid NOT NULL,
          PRIMARY KEY(release_key,profile_key),
          FOREIGN KEY(release_key,configuration_key,snapshot_id)
            REFERENCES retrieval_releases(
              release_key,configuration_key,snapshot_id
            )
            ON DELETE CASCADE,
          FOREIGN KEY(configuration_key,profile_key)
            REFERENCES retrieval_configuration_members(configuration_key,profile_key),
          FOREIGN KEY(build_id,profile_key,snapshot_id)
            REFERENCES retrieval_index_builds(build_id,profile_key,snapshot_id)
        )
        """,
        """
        CREATE TABLE active_retrieval_release (
          singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
          release_key text NOT NULL UNIQUE,
          release_state text NOT NULL DEFAULT 'ready' CHECK(release_state='ready'),
          updated_at timestamptz NOT NULL DEFAULT now(),
          FOREIGN KEY(release_key,release_state)
            REFERENCES retrieval_releases(release_key,state)
        )
        """,
        """
        CREATE INDEX retrieval_index_builds_profile_snapshot_state
        ON retrieval_index_builds(profile_key,snapshot_id,state,started_at DESC)
        """,
        """
        CREATE INDEX retrieval_releases_snapshot_state
        ON retrieval_releases(snapshot_id,state,created_at DESC)
        """,
        """
        ALTER TABLE evaluation_runs
          ADD COLUMN dataset_sha256 text
            CHECK(dataset_sha256 IS NULL OR dataset_sha256 ~ '^[0-9a-f]{64}$'),
          ADD COLUMN code_sha256 text
            CHECK(code_sha256 IS NULL OR code_sha256 ~ '^[0-9a-f]{64}$'),
          ADD COLUMN corpus_snapshot_id text REFERENCES corpus_snapshots(snapshot_id),
          ADD COLUMN retrieval_release_key text,
          ADD COLUMN run_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
            CHECK(jsonb_typeof(run_metadata)='object'),
          ADD CONSTRAINT evaluation_runs_release_snapshot_fk
            FOREIGN KEY(retrieval_release_key,corpus_snapshot_id)
            REFERENCES retrieval_releases(release_key,snapshot_id),
          ADD CONSTRAINT evaluation_runs_release_requires_snapshot
            CHECK(retrieval_release_key IS NULL OR corpus_snapshot_id IS NOT NULL)
        """,
        """
        CREATE INDEX evaluation_runs_retrieval_provenance
        ON evaluation_runs(corpus_snapshot_id,retrieval_release_key,created_at DESC)
        WHERE corpus_snapshot_id IS NOT NULL
        """,
        f"""
        INSERT INTO runtime_flags(key,value,updated_at)
        VALUES(
          '{_CAPABILITY_KEY}',
          jsonb_build_object('enabled',true,'migration','0011'),
          now()
        )
        ON CONFLICT(key) DO UPDATE
        SET value=excluded.value,updated_at=now()
        """,
    ]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    raise RuntimeError(
        "0011 records corpus/retriever/evaluation provenance; "
        "automatic downgrade would discard that provenance"
    )
