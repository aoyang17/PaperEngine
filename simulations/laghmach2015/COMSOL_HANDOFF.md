# COMSOL 远程执行交接清单

当前源代码已经完成本地公式、量纲、后处理和 shell 语法检查，但没有在 COMSOL 6.4 中编译。以下每一关都必须保留日志；上一关失败时不得提交大矩阵。

## 0. 主机身份

本地 `known_hosts` 记录的旧 ECDSA 指纹为：

`SHA256:VuBzFENIIv1QjG5M6o7Wbtqo+7DqBosvYewnR5DGC+I`

远端当前呈现的新 ECDSA 指纹为：

`SHA256:I0memwTrnIz1tzeglzVhT5RexILj5trEl55Wd1Hfe2k`

必须先由服务器管理员或另一条可信渠道确认新指纹。不能仅因为 IP 和端口看起来正确就删除旧记录或接受新密钥。

## 1. 编译与 1 tau1 smoke solve

确认主机身份并上传 `comsol/` 目录后，在远端创建专用目录，并运行：

```bash
remote_case_root="$(pwd -P)/aobo/comsol_cases/laghmach2015"
bash stage_smoke.sh "$remote_case_root/smoke"
```

验收：

- `comsol compile` 返回 0；
- batch 返回 0；
- `smoke_built.mph`、`smoke_solved.mph`、CSV 和 batch log 均非空；
- CSV 中所有列有限，且同时存在 `incompL2` 和 `incompMax`；
- 相场弱式的梯度、势垒和驱动力都保留 `/tau1`。

## 2. 核心矩阵

```bash
bash stage_core_matrix.sh "$remote_case_root/core"
```

等待 `baseline`、`control`、`fine_grid`、`half_timestep` 四个 Slurm 任务全部结束。每个任务必须有 solved MPH、CSV、COMSOL batch log、Slurm stdout/stderr 和退出状态。

## 3. 阈值与双晶核表面能矩阵

```bash
bash stage_threshold_matrix.sh "$remote_case_root/threshold"
bash stage_surface_matrix.sh "$remote_case_root/surface"
```

阈值矩阵覆盖 `(298 K, lambda 2/3)`、`(303 K, lambda 3/4)`、`(308 K, lambda 4/5)`；表面能矩阵在 `303 K, lambda=6` 下覆盖 `Rn=5/9 nm`。

## 4. 下载与本地机器验收

将整个远端 `laghmach2015` 结果树复制到 `/home/aobo/paper-engine/tmp/runs/comsol/laghmach2015/suite`，然后执行：

```bash
LAGHMACH_PYTHON_BIN=/mnt/data2/aobo/envs/NaGen/bin/python \
  bash simulations/laghmach2015/evaluate_comsol_suite.sh \
  tmp/runs/comsol/laghmach2015/suite \
  tmp/runs/comsol/laghmach2015/final
```

只有 `comsol_acceptance.json` 的 `passed=true`、22/22 必选指标通过，且每个结果都能追溯到日志、CSV 和 solved MPH，才可以称为“第一阶段初步复现成功”。各向异性 5 项仍作为第二阶段单独报告。
