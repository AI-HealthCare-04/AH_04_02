"""add refresh_tokens table and secure invitations columns

Revision ID: d9616a377d8c
Revises: bcdbae97c089
Create Date: 2026-07-15 15:20:06.937820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # [2026-07-14] SQLModel 커스텀 컬럼 타입(AutoString 등) autogenerate가 참조하므로 항상 import


# revision identifiers, used by Alembic.
revision: str = 'd9616a377d8c'
down_revision: Union[str, Sequence[str], None] = 'bcdbae97c089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    [2026-07-15] 보안 검토(REQ-001/002/003) 반영:
    - refresh_tokens: refresh 토큰 회전/재사용 탐지용 신규 테이블(신규라 데이터 이전 불필요).
    - invitations: token(평문) -> token_hash(HMAC 해시), invited_phone(평문) ->
      invited_phone_encrypted(Fernet 암호화), expires_at(만료시각) 추가. 팀 공통 DB에
      이미 있는 행이 있으면 원본 값을 새 컬럼으로 옮겨서 기존 초대 링크가 계속
      동작하게 한 다음 원본 컬럼을 제거한다(해시/암호화는 역산 불가라 downgrade에서는
      복구하지 못하고 새로 발급해야 함 — 아래 downgrade() 참고).
    """
    op.create_table(
        'refresh_tokens',
        sa.Column('jti', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('jti'),
    )

    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('invited_phone_encrypted', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(), nullable=True))

    # 기존 행의 원본 token/invited_phone을 새 컬럼으로 이전(있는 경우만 — 새 설치면 0행).
    connection = op.get_bind()
    existing_rows = connection.execute(sa.text("SELECT id, token, invited_phone FROM invitations")).fetchall()
    if existing_rows:
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from core.security import encrypt_pii, hash_token

        for row in existing_rows:
            connection.execute(
                sa.text(
                    "UPDATE invitations SET token_hash = :token_hash, invited_phone_encrypted = :phone WHERE id = :id"
                ),
                {
                    "token_hash": hash_token(row.token) if row.token else None,
                    "phone": encrypt_pii(row.invited_phone) if row.invited_phone else None,
                    "id": row.id,
                },
            )

    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.alter_column('token_hash', existing_type=sqlmodel.sql.sqltypes.AutoString(), nullable=False)
        # 원본 token 컬럼에 걸려있던 유니크 인덱스도 같이 없애야 한다 — 안 그러면 SQLite
        # batch 모드가 테이블을 재생성할 때 이미 없는 컬럼을 가리키는 인덱스를 다시
        # 만들려다 실패한다.
        batch_op.drop_index('ix_invitations_token')
        batch_op.drop_column('token')
        batch_op.drop_column('invited_phone')
        batch_op.create_index('ix_invitations_token_hash', ['token_hash'], unique=True)


def downgrade() -> None:
    """Downgrade schema.

    ⚠️ token_hash는 해시라 원본 token을 복구할 수 없다 — 다운그레이드 후 기존 초대는
    링크가 무효화되며, 필요하면 새로 발급해야 한다(invited_phone도 마찬가지로 암호문을
    평문으로 되돌리지 않고 그냥 버린다 — 이 방향 전환 자체가 예외적인 상황이라 가정).
    """
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.drop_index('ix_invitations_token_hash')
        batch_op.add_column(sa.Column('token', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('invited_phone', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        # [수정] upgrade()가 이 인덱스를 drop_index('ix_invitations_token')으로 지우고
        # 시작하므로, downgrade에서도 다시 만들어둬야 그 다음 upgrade가 또 정상 동작한다
        # (안 만들면 downgrade -> upgrade 왕복 시 "No such index" 에러로 깨짐).
        batch_op.create_index('ix_invitations_token', ['token'], unique=True)
        batch_op.drop_column('token_hash')
        batch_op.drop_column('invited_phone_encrypted')
        batch_op.drop_column('expires_at')

    op.drop_table('refresh_tokens')
