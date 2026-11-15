# Snowflake ML

Snowflake ML is the set of Python libraries, compute runtimes, and governed objects for building, deploying, and operating machine learning models inside Snowflake. Its main value for architects is that features, training, model artifacts, inference, and monitoring all live under the same RBAC, lineage, and network boundary as the data, which removes most of the data movement and duplicated governance of an external ML stack.

## How it works

The platform is a set of components, delivered mostly through the `snowflake-ml-python` package:

- **Development and training compute**: Notebooks on the Container Runtime run on compute pools (CPU or GPU), including the system pools `SYSTEM_COMPUTE_POOL_CPU` and `SYSTEM_COMPUTE_POOL_GPU`. They support open-source frameworks and distributed training. ML Jobs let you submit training code from any IDE to the same runtime. Warehouse-based Snowpark is still useful for preprocessing and for models that fit warehouse constraints.
- **Feature Store**: entities and feature views (backed by dynamic tables or views) give point-in-time-correct training sets and consistent features at inference time. Hybrid tables or a Postgres-backed store can provide online serving, with different feature support.
- **Model Registry**: models are first-class schema-level objects. You log them with `Registry.log_model`, which captures dependencies, signatures, metrics, and the task type. Built-in handlers cover scikit-learn, XGBoost, LightGBM, PyTorch, TensorFlow, Hugging Face pipelines, MLflow pyfunc, and others, and custom models are supported. Documented limits include 1,000 versions per model, 10 methods per version, and 15 GB total model size for warehouse-deployed models.
- **Inference targets**: run model methods on a warehouse from SQL or Python, or deploy to Snowpark Container Services (`create_service`) for GPU and real-time HTTP inference, or use `run_batch` for batch jobs on a compute pool. `target_platforms` controls where a version can run, and `log_model` fails if you require WAREHOUSE and the model cannot run there.
- **Governance and operations**: USAGE on a model allows warehouse inference without exposing internals. READ also allows SPCS inference and viewing metadata. Version aliases (including the system aliases DEFAULT, FIRST, and LAST), tags, and default versions support promotion workflows. ML Observability monitors drift and performance, and it requires the `task` to be set when you log the model.

Dependency resolution is a key design decision. Warehouse execution uses the Snowflake Conda channel, while pip packages need an artifact repository (the built-in PyPI repository or a customer-hosted one).

## Example

Train with scikit-learn, log the model with metrics, and promote it:

```python
from snowflake.ml.registry import Registry
from snowflake.ml.model import task
from sklearn.ensemble import GradientBoostingClassifier

train_pdf = session.table("ML.FEATURES.CHURN_TRAIN").to_pandas()
X, y = train_pdf.drop(columns=["CHURNED"]), train_pdf["CHURNED"]
clf = GradientBoostingClassifier().fit(X, y)

reg = Registry(session=session, database_name="ML", schema_name="REGISTRY")
mv = reg.log_model(
    clf,
    model_name="churn_model",
    version_name="v3",
    conda_dependencies=["scikit-learn"],
    sample_input_data=X.head(100),
    metrics={"auc": 0.91},
    task=task.Task.TABULAR_BINARY_CLASSIFICATION,
    comment="GBM on 2026 Q3 features",
)
reg.get_model("churn_model").default = "v3"
```

Score in SQL using the model's default version:

```sql
SELECT customer_id,
       churn_model!PREDICT(tenure_months, monthly_spend, support_calls) AS prediction
FROM ml.features.churn_scoring;
```

## Best practices

- Use dedicated registry schemas per environment (for example `ML_DEV.REGISTRY` and `ML_PROD.REGISTRY`) and promote versions through CI instead of retraining in production.
- Always pass `sample_input_data` or explicit signatures and set `task`, so that signatures are typed and observability works.
- Build features once in the Feature Store on top of curated layers, so training and inference share definitions and point-in-time logic.
- Choose the inference target deliberately: warehouse for batch SQL scoring at scale with simple dependencies, SPCS for GPUs, large models, custom runtimes, or low-latency HTTP endpoints.
- Grant consumers USAGE rather than READ unless they need SPCS inference or metadata. Restrict USAGE on the system GPU pool so GPU spend stays controlled.
- Pin dependency versions and use artifact repositories for private packages to keep builds reproducible.

## Common pitfalls

- Pulling an entire large table into pandas on a notebook node. Push filtering and aggregation down into Snowpark first.
- Logging custom models without declaring every dependency, then hitting import errors at inference time.
- Using VOLATILE model methods inside dynamic tables and getting forced full refreshes.
- Assuming models trained with built-in ML functions such as FORECAST appear in the Model Registry. They do not.
- Leaving SPCS inference services and GPU pools running after experiments, which accrues cost while idle.

## Learn more

- [Snowflake Model Registry](https://docs.snowflake.com/en/developer-guide/snowflake-ml/model-registry/overview)
- [Online serving with hybrid tables](https://docs.snowflake.com/en/developer-guide/snowflake-ml/feature-store/online-feature-store-hybrid-tables)

## Knowledge check

### A 20 GB transformer model needs GPU inference behind an HTTP endpoint. Which deployment target fits?
- [ ] Log the model with target_platforms set to WAREHOUSE and call it from SQL
- [x] Log it for Snowpark Container Services and deploy it with create_service on a GPU compute pool
- [ ] Convert it to a Python UDF
- [ ] Use AI_COMPLETE with the model name
> Warehouse-deployed models are limited to 15 GB and do not provide GPUs. SPCS model serving supports GPU compute pools and HTTP ingress.

### A BI team should run churn predictions from SQL but must not inspect model metrics or artifacts. Which privilege should their role receive on the model?
- [ ] OWNERSHIP
- [ ] READ
- [x] USAGE
- [ ] MONITOR
> USAGE allows warehouse inference without access to internals. READ additionally exposes metadata such as metrics and enables SPCS inference.

### Why should feature engineering for both training and online scoring be defined in the Feature Store rather than separately in notebooks and application code?
- [ ] Feature views make models train faster on GPUs
- [x] Shared feature view definitions with point-in-time joins prevent training and serving skew and label leakage
- [ ] The Model Registry rejects models trained without the Feature Store
- [ ] Feature views are required for ML Observability
> Defining features once and generating point-in-time-correct training sets keeps training and inference consistent, which is a common source of silent model degradation.
